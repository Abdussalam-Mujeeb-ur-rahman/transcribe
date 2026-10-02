package dev.transcribelab.android

import com.google.android.gms.tasks.Task
import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.nl.translate.TranslateLanguage
import com.google.mlkit.nl.translate.Translation
import com.google.mlkit.nl.translate.TranslatorOptions
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withTimeout
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Keeps whole spoken sentences together while retaining their approximate audio range. */
internal fun sentenceChunks(segments: List<Segment>): List<Segment> {
    val chunks = mutableListOf<Segment>()
    var start = 0f
    var end = 0f
    val text = StringBuilder()
    for (segment in segments) {
        val words = segment.text.trim()
        if (words.isEmpty()) continue
        if (text.isEmpty()) start = segment.startSeconds else text.append(' ')
        text.append(words)
        end = segment.endSeconds
        if (words.last() in ".?!。！？" || text.length >= 350) {
            chunks += Segment(start, end, text.toString())
            text.clear()
        }
    }
    if (text.isNotEmpty()) chunks += Segment(start, end, text.toString())
    return chunks
}

internal object LocalTextTranslator {
    suspend fun toEnglish(
        source: List<Segment>,
        sourceLanguage: String,
        onModelReady: () -> Unit,
        onChunk: (done: Int, total: Int) -> Unit,
    ): List<Segment> {
        if (sourceLanguage == TranslateLanguage.ENGLISH) return source
        val language = TranslateLanguage.fromLanguageTag(sourceLanguage)
            ?: throw IllegalStateException("On-device text translation does not support '$sourceLanguage'. The original transcript is still available.")
        val translator = Translation.getClient(
            TranslatorOptions.Builder()
                .setSourceLanguage(language)
                .setTargetLanguage(TranslateLanguage.ENGLISH)
                .build(),
        )
        try {
            try {
                withTimeout(60_000) {
                    translator.downloadModelIfNeeded(DownloadConditions.Builder().build()).awaitResult()
                }
            } catch (_: TimeoutCancellationException) {
                throw IllegalStateException(
                    "The on-device translation model was not ready in time. Check the connection and retry"
                )
            }
            onModelReady()
            val chunks = sentenceChunks(source)
            return chunks.mapIndexed { index, chunk ->
                currentCoroutineContext().ensureActive()
                val english = try {
                    withTimeout(30_000) { translator.translate(chunk.text).awaitResult().trim() }
                } catch (_: TimeoutCancellationException) {
                    throw IllegalStateException("The on-device text translation took too long")
                }
                check(english.isNotEmpty()) { "The on-device text translator returned an empty result." }
                onChunk(index + 1, chunks.size)
                chunk.copy(text = english)
            }
        } finally {
            translator.close()
        }
    }
}

private suspend fun <T> Task<T>.awaitResult(): T = suspendCancellableCoroutine { continuation ->
    addOnSuccessListener { result ->
        if (continuation.isActive) continuation.resume(result)
    }
    addOnFailureListener { error ->
        if (continuation.isActive) continuation.resumeWithException(error)
    }
    addOnCanceledListener {
        continuation.cancel()
    }
}
