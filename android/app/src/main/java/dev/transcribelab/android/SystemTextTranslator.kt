package dev.transcribelab.android

import android.content.Context
import android.os.Build
import android.os.CancellationSignal
import android.view.translation.TranslationContext
import android.view.translation.TranslationManager
import android.view.translation.TranslationRequest
import android.view.translation.TranslationRequestValue
import android.view.translation.TranslationResponse
import android.view.translation.TranslationResponseValue
import android.view.translation.TranslationSpec
import android.view.translation.Translator
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.coroutines.resume

/** Uses an already-installed Android language pack; it never sends text to a network service. */
internal object SystemTextTranslator {
    suspend fun toEnglishIfAvailable(
        context: Context,
        source: List<Segment>,
        sourceLanguage: String,
        onReady: () -> Unit,
        onChunk: (done: Int, total: Int) -> Unit,
    ): List<Segment>? {
        if (Build.VERSION.SDK_INT < 31) return null
        val manager = context.getSystemService(TranslationManager::class.java) ?: return null
        val capability = withContext(Dispatchers.IO) {
            manager.getOnDeviceTranslationCapabilities(
                TranslationSpec.DATA_FORMAT_TEXT, TranslationSpec.DATA_FORMAT_TEXT,
            ).filter {
                it.sourceSpec.locale.language == sourceLanguage &&
                    it.targetSpec.locale.language == "en"
            }.maxByOrNull { it.state == android.view.translation.TranslationCapability.STATE_ON_DEVICE }
        } ?: return null
        val translationContext = TranslationContext.Builder(
            capability.sourceSpec, capability.targetSpec,
        ).build()
        val translator = try {
            withTimeout(20_000) {
                suspendCancellableCoroutine<Translator?> { continuation ->
                    manager.createOnDeviceTranslator(translationContext, context.mainExecutor) { created ->
                        if (continuation.isActive) continuation.resume(created)
                        else created?.destroy()
                    }
                }
            }
        } catch (_: TimeoutCancellationException) {
            throw IllegalStateException("The system's on-device translator did not start in time")
        } ?: return null
        try {
            onReady()
            val chunks = sentenceChunks(source)
            return chunks.mapIndexed { index, chunk ->
                val request = TranslationRequest.Builder()
                    .setTranslationRequestValues(listOf(TranslationRequestValue.forText(chunk.text)))
                    .build()
                val signal = CancellationSignal()
                val response = try {
                    withTimeout(30_000) {
                        suspendCancellableCoroutine<TranslationResponse> { continuation ->
                            continuation.invokeOnCancellation { signal.cancel() }
                            translator.translate(request, signal, context.mainExecutor) { result ->
                                if (continuation.isActive) continuation.resume(result)
                            }
                        }
                    }
                } catch (_: TimeoutCancellationException) {
                    throw IllegalStateException("The system's on-device translation took too long")
                }
                val value = response.translationResponseValues[0]
                check(value?.statusCode == TranslationResponseValue.STATUS_SUCCESS) {
                    "The system's on-device translator could not translate this text."
                }
                val english = value.text?.toString()?.trim().orEmpty()
                check(english.isNotEmpty()) { "The system's on-device translator returned an empty result." }
                onChunk(index + 1, chunks.size)
                chunk.copy(text = english)
            }
        } finally {
            translator.destroy()
        }
    }
}
