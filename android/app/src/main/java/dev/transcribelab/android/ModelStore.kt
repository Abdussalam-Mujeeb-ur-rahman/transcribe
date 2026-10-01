package dev.transcribelab.android

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import kotlin.coroutines.coroutineContext

enum class ModelChoice(
    val fileName: String,
    val displayName: String,
    val downloadMiB: Int,
    val expectedSha1: String,
) {
    BASE(
        "ggml-base.bin",
        "Base · faster",
        142,
        "465707469ff3a37a2b9b8d8f89f2f99de7299dac",
    ),
    SMALL(
        "ggml-small.bin",
        "Small · larger, slower",
        466,
        "55356645c2b361a969dfd0ef2c5a50d530afd8d5",
    ),
}

object ModelStore {
    private const val modelBaseUrl = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"
    private const val mebibyte = 1024L * 1024L

    private fun modelDirectory(context: Context) = File(context.filesDir, "models")

    fun modelFile(context: Context, choice: ModelChoice) = File(modelDirectory(context), choice.fileName)

    suspend fun installed(context: Context, choice: ModelChoice): Boolean = withContext(Dispatchers.IO) {
        val file = modelFile(context, choice)
        val expectedBytes = choice.downloadMiB * mebibyte
        file.isFile && file.length() in (expectedBytes - 2 * mebibyte)..(expectedBytes + 2 * mebibyte) &&
            sha1(file) == choice.expectedSha1
    }

    suspend fun download(context: Context, choice: ModelChoice, onProgress: (Int) -> Unit): File =
        withContext(Dispatchers.IO) {
            if (installed(context, choice)) return@withContext modelFile(context, choice)

            val directory = modelDirectory(context)
            check(directory.exists() || directory.mkdirs()) { "Could not create the model folder." }
            val maximumBytes = (choice.downloadMiB + 16L) * mebibyte
            check(directory.usableSpace > maximumBytes + 64 * mebibyte) {
                "There is not enough free space for the ${choice.displayName} model."
            }

            val partial = File(directory, "${choice.fileName}.part")
            val connection = (URL(modelBaseUrl + choice.fileName).openConnection() as HttpURLConnection).apply {
                connectTimeout = 20_000
                readTimeout = 30_000
                instanceFollowRedirects = true
            }

            try {
                check(connection.responseCode == HttpURLConnection.HTTP_OK) {
                    "The model download failed (HTTP ${connection.responseCode})."
                }
                val expectedLength = connection.contentLengthLong
                check(expectedLength <= 0 || expectedLength <= maximumBytes) {
                    "The model download is larger than expected."
                }
                val digest = MessageDigest.getInstance("SHA-1")
                var downloaded = 0L
                connection.inputStream.use { input ->
                    partial.outputStream().buffered().use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            coroutineContext.ensureActive()
                            val count = input.read(buffer)
                            if (count < 0) break
                            downloaded += count
                            check(downloaded <= maximumBytes) {
                                "The model download is larger than expected."
                            }
                            output.write(buffer, 0, count)
                            digest.update(buffer, 0, count)
                            if (expectedLength > 0) {
                                onProgress(((downloaded * 100) / expectedLength).toInt().coerceIn(0, 99))
                            }
                        }
                    }
                }
                check(downloaded >= (choice.downloadMiB - 2L) * mebibyte) {
                    "The model download is incomplete."
                }
                val actualSha1 = digest.digest().joinToString("") { "%02x".format(it) }
                check(actualSha1 == choice.expectedSha1) { "The downloaded model failed its integrity check." }
                val model = modelFile(context, choice)
                check(!model.exists() || model.delete()) { "Could not replace the old model." }
                check(partial.renameTo(model)) { "Could not save the downloaded model." }
                onProgress(100)
                model
            } finally {
                connection.disconnect()
                if (partial.exists()) partial.delete()
            }
        }

    private fun sha1(file: File): String {
        val digest = MessageDigest.getInstance("SHA-1")
        file.inputStream().buffered().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
