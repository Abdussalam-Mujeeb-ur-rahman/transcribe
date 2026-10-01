package dev.transcribelab.android

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.provider.OpenableColumns
import android.os.SystemClock
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.coroutines.coroutineContext
import kotlin.math.min

object AudioPipeline {
    const val maximumMinutes = 10
    private const val maximumInputBytes = 100L * 1024 * 1024
    private const val targetRate = 16_000
    private const val maximumSamples = targetRate * maximumMinutes * 60

    fun displayName(context: Context, uri: Uri): String {
        try {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
                ?.use { cursor ->
                    if (cursor.moveToFirst()) {
                        val column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                        if (column >= 0) return cursor.getString(column)
                    }
                }
        } catch (_: SecurityException) {
            // A sender may omit the temporary permission; decoding reports a clearer error.
        }
        return uri.lastPathSegment?.substringAfterLast('/') ?: "Voice note"
    }

    suspend fun decode(context: Context, uri: Uri): FloatArray = withContext(Dispatchers.IO) {
        val source = copyIntoPrivateCache(context, uri)
        try {
            decodePrivateFile(source)
        } finally {
            source.delete()
        }
    }

    private suspend fun copyIntoPrivateCache(context: Context, uri: Uri): File {
        val originalName = displayName(context, uri)
        val extension = originalName.substringAfterLast('.', "audio")
            .take(8).filter { it.isLetterOrDigit() }.ifEmpty { "audio" }
        val copy = File.createTempFile("transcribe-import-", ".$extension", context.cacheDir)
        try {
            val input = context.contentResolver.openInputStream(uri)
                ?: error("This voice note could not be opened.")
            var copied = 0L
            input.use { source ->
                copy.outputStream().buffered().use { target ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        coroutineContext.ensureActive()
                        val count = source.read(buffer)
                        if (count < 0) break
                        copied += count
                        check(copied <= maximumInputBytes) {
                            "This prototype accepts recordings up to 100 MB."
                        }
                        target.write(buffer, 0, count)
                    }
                }
            }
            check(copied > 0) { "The shared voice note is empty." }
            return copy
        } catch (error: Exception) {
            copy.delete()
            if (error is SecurityException) {
                throw IllegalStateException(
                    "This recording could not be opened. Share it again or use Choose voice note.",
                    error,
                )
            }
            throw error
        }
    }

    private suspend fun decodePrivateFile(file: File): FloatArray {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        var started = false
        try {
            extractor.setDataSource(file.absolutePath)
            val audioTrack = (0 until extractor.trackCount).firstOrNull { index ->
                extractor.getTrackFormat(index).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true
            } ?: error("This file does not contain a supported audio track.")
            val inputFormat = extractor.getTrackFormat(audioTrack)
            val mime = inputFormat.getString(MediaFormat.KEY_MIME)
                ?: error("The audio format could not be identified.")
            extractor.selectTrack(audioTrack)

            codec = MediaCodec.createDecoderByType(mime)
            codec.configure(inputFormat, null, null, 0)
            codec.start()
            started = true

            val output = FloatCollector(maximumSamples)
            var converter: RateConverter? = null
            var channels = 0
            var pcmEncoding = AudioFormat.ENCODING_PCM_16BIT
            var inputFinished = false
            var outputFinished = false
            var lastMovement = SystemClock.elapsedRealtime()
            val info = MediaCodec.BufferInfo()

            while (!outputFinished) {
                coroutineContext.ensureActive()
                if (SystemClock.elapsedRealtime() - lastMovement > 60_000) {
                    error("Audio decoding stalled. Try another recording.")
                }

                if (!inputFinished) {
                    val index = codec.dequeueInputBuffer(10_000)
                    if (index >= 0) {
                        val buffer = codec.getInputBuffer(index)
                            ?: error("The audio decoder has no input buffer.")
                        buffer.clear()
                        val size = extractor.readSampleData(buffer, 0)
                        if (size < 0) {
                            codec.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputFinished = true
                        } else {
                            codec.queueInputBuffer(index, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                        lastMovement = SystemClock.elapsedRealtime()
                    }
                }

                when (val index = codec.dequeueOutputBuffer(info, 10_000)) {
                    MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        val format = codec.outputFormat
                        val sampleRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                        val newChannels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                        check(newChannels in 1..8) { "The audio has an unsupported channel count." }
                        check(converter == null || converter.sourceRate == sampleRate) {
                            "The recording changes sample rate during playback."
                        }
                        converter = RateConverter(sampleRate, output)
                        channels = newChannels
                        pcmEncoding = if (format.containsKey(MediaFormat.KEY_PCM_ENCODING)) {
                            format.getInteger(MediaFormat.KEY_PCM_ENCODING)
                        } else {
                            AudioFormat.ENCODING_PCM_16BIT
                        }
                        check(pcmEncoding == AudioFormat.ENCODING_PCM_16BIT ||
                            pcmEncoding == AudioFormat.ENCODING_PCM_FLOAT) {
                            "The decoder produced an unsupported audio format."
                        }
                        lastMovement = SystemClock.elapsedRealtime()
                    }

                    MediaCodec.INFO_TRY_AGAIN_LATER -> Unit

                    else -> if (index >= 0) {
                        if (info.size > 0) {
                            val activeConverter = converter
                                ?: error("The audio decoder did not report its output format.")
                            val buffer = codec.getOutputBuffer(index)
                                ?: error("The audio decoder has no output buffer.")
                            buffer.position(info.offset)
                            buffer.limit(info.offset + info.size)
                            appendPcm(buffer.slice().order(ByteOrder.LITTLE_ENDIAN), channels,
                                pcmEncoding, activeConverter)
                        }
                        codec.releaseOutputBuffer(index, false)
                        outputFinished = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                        lastMovement = SystemClock.elapsedRealtime()
                    }
                }
            }
            converter?.finish()
            check(output.size > 0) { "The recording contains no decodable speech audio." }
            return output.toArray()
        } finally {
            if (started) codec?.stop()
            codec?.release()
            extractor.release()
        }
    }

    private fun appendPcm(buffer: ByteBuffer, channels: Int, encoding: Int, converter: RateConverter) {
        val bytesPerSample = if (encoding == AudioFormat.ENCODING_PCM_FLOAT) 4 else 2
        val bytesPerFrame = bytesPerSample * channels
        while (buffer.remaining() >= bytesPerFrame) {
            var mono = 0f
            repeat(channels) {
                mono += if (encoding == AudioFormat.ENCODING_PCM_FLOAT) {
                    buffer.float
                } else {
                    buffer.short / 32768f
                }
            }
            converter.add(mono / channels)
        }
    }

    private class FloatCollector(private val maximum: Int) {
        private var values = FloatArray(targetRate * 15)
        var size = 0
            private set

        fun add(value: Float) {
            check(size < maximum) {
                "This prototype supports voice notes up to $maximumMinutes minutes."
            }
            if (size == values.size) values = values.copyOf(min(maximum, values.size * 2))
            values[size++] = value
        }

        fun toArray(): FloatArray = values.copyOf(size)
    }

    private class RateConverter(val sourceRate: Int, private val output: FloatCollector) {
        init {
            check(sourceRate in 8_000..192_000) { "The audio sample rate is unsupported." }
        }

        private val sourceFramesPerOutput = sourceRate.toDouble() / targetRate
        private var sourceFrame = 0L
        private var nextBoundary = sourceFramesPerOutput
        private var weightedSum = 0.0
        private var totalWeight = 0.0

        fun add(sample: Float) {
            var position = sourceFrame.toDouble()
            val frameEnd = position + 1.0
            while (position < frameEnd - 0.0000001) {
                val end = min(frameEnd, nextBoundary)
                val weight = end - position
                weightedSum += sample * weight
                totalWeight += weight
                position = end
                if (position >= nextBoundary - 0.0000001) {
                    output.add((weightedSum / totalWeight).toFloat())
                    weightedSum = 0.0
                    totalWeight = 0.0
                    nextBoundary += sourceFramesPerOutput
                }
            }
            sourceFrame++
        }

        fun finish() {
            if (totalWeight > 0) output.add((weightedSum / totalWeight).toFloat())
        }
    }
}
