package dev.transcribelab.android

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class Stage { CHECKING, READY, DOWNLOADING, PREPARING, PROCESSING, TRANSLATING, DONE, ERROR }
enum class TaskMode { TRANSCRIBE, TRANSLATE_TO_ENGLISH }

data class ScreenState(
    val stage: Stage = Stage.CHECKING,
    val availableModels: Set<ModelChoice> = emptySet(),
    val modelChoice: ModelChoice = ModelChoice.BASE,
    val modelProgress: Int = 0,
    val fileName: String? = null,
    val mediaUri: Uri? = null,
    val mode: TaskMode = TaskMode.TRANSCRIBE,
    val sourceLanguage: String = "auto",
    val speechHint: String = "",
    val outputFormat: OutputFormat = OutputFormat.TXT,
    val progress: Int = 0,
    val segments: List<Segment> = emptyList(),
    val originalSegments: List<Segment> = emptyList(),
    val detectedLanguage: String = "",
    val resultIsTranslation: Boolean = false,
    val translationProvider: String = "",
    val message: String = "",
) {
    val modelReady: Boolean get() = modelChoice in availableModels
    val outputText: String get() = TranscriptFormats.render(segments, outputFormat)
}

class TranscribeViewModel(application: Application) : AndroidViewModel(application) {
    private val context get() = getApplication<Application>()
    private val bridge = WhisperBridge()
    private val mutableState = MutableStateFlow(ScreenState())
    val state = mutableState.asStateFlow()
    private var selectedUri: Uri? = null
    private var activeJob: Job? = null
    private var cancelRequested = false

    init {
        viewModelScope.launch {
            val ready = ModelChoice.entries.filter { choice ->
                try {
                    ModelStore.installed(context, choice)
                } catch (_: Exception) {
                    false
                }
            }.toSet()
            mutableState.update { it.copy(stage = Stage.READY, availableModels = ready) }
        }
    }

    fun select(uri: Uri) {
        if (busy()) return
        selectedUri = uri
        mutableState.update {
            it.copy(
                stage = Stage.READY,
                fileName = AudioPipeline.displayName(context, uri),
                mediaUri = uri,
                segments = emptyList(),
                originalSegments = emptyList(),
                detectedLanguage = "",
                resultIsTranslation = false,
                translationProvider = "",
                message = "",
                progress = 0,
            )
        }
    }

    fun setMode(mode: TaskMode) {
        if (busy()) return
        mutableState.update { current ->
            if (current.mode == mode) current else current.copy(
                mode = mode,
                stage = Stage.READY,
                segments = emptyList(),
                originalSegments = emptyList(),
                detectedLanguage = "",
                resultIsTranslation = false,
                translationProvider = "",
                message = "Run again for the selected mode.",
            )
        }
    }

    fun setLanguage(language: String) {
        if (busy() || language !in supportedLanguages.map { it.code }) return
        mutableState.update { current ->
            if (current.sourceLanguage == language) current else current.copy(
                sourceLanguage = language,
                stage = Stage.READY,
                segments = emptyList(),
                originalSegments = emptyList(),
                detectedLanguage = "",
                resultIsTranslation = false,
                translationProvider = "",
                message = "Run again for the selected language.",
            )
        }
    }

    fun setModel(choice: ModelChoice) {
        if (busy()) return
        mutableState.update { current ->
            if (current.modelChoice == choice) current else current.copy(
                modelChoice = choice,
                stage = Stage.READY,
                segments = emptyList(),
                originalSegments = emptyList(),
                detectedLanguage = "",
                resultIsTranslation = false,
                translationProvider = "",
                message = "Run again with the selected model.",
            )
        }
    }

    fun setSpeechHint(hint: String) {
        if (busy()) return
        mutableState.update { it.copy(speechHint = hint.take(200)) }
    }

    fun setOutputFormat(format: OutputFormat) {
        if (busy()) return
        mutableState.update { it.copy(outputFormat = format) }
    }

    fun editSegment(index: Int, text: String) {
        if (mutableState.value.stage != Stage.DONE) return
        mutableState.update { current ->
            current.copy(segments = current.segments.mapIndexed { position, segment ->
                if (position == index) segment.copy(text = text) else segment
            })
        }
    }

    fun downloadModel() {
        if (busy() || mutableState.value.modelReady) return
        val choice = mutableState.value.modelChoice
        activeJob = viewModelScope.launch {
            mutableState.update { it.copy(stage = Stage.DOWNLOADING, modelProgress = 0, message = "") }
            try {
                ModelStore.download(context, choice) { percent ->
                    mutableState.update { it.copy(modelProgress = percent) }
                }
                mutableState.update {
                    it.copy(stage = Stage.READY, availableModels = it.availableModels + choice)
                }
            } catch (_: CancellationException) {
                mutableState.update { it.copy(stage = Stage.READY, message = "Download cancelled.") }
            } catch (error: Exception) {
                mutableState.update {
                    it.copy(stage = Stage.ERROR, message = error.message ?: "The model download failed.")
                }
            } finally {
                activeJob = null
            }
        }
    }

    fun run() {
        val uri = selectedUri ?: return
        if (busy()) return
        val settings = mutableState.value
        if (!settings.modelReady) {
            mutableState.update { it.copy(message = "Download the selected model first.") }
            return
        }
        cancelRequested = false
        activeJob = viewModelScope.launch {
            mutableState.update {
                it.copy(stage = Stage.PREPARING, progress = 0, message = "", segments = emptyList(),
                    originalSegments = emptyList(), detectedLanguage = "",
                    resultIsTranslation = false, translationProvider = "")
            }
            try {
                val samples = AudioPipeline.decode(context, uri)
                val model = ModelStore.modelFile(context, settings.modelChoice)
                mutableState.update { it.copy(stage = Stage.PROCESSING) }
                val result = withContext(Dispatchers.Default) {
                    bridge.process(
                        model.absolutePath,
                        samples,
                        settings.sourceLanguage,
                        settings.speechHint.trim(),
                    ) { percent ->
                        mutableState.update { it.copy(progress = percent) }
                    }
                }
                check(result.segments.any { it.text.isNotBlank() }) { "No speech was detected in this recording." }
                mutableState.update {
                    it.copy(originalSegments = result.segments, detectedLanguage = result.language)
                }
                val shouldTranslate = settings.mode == TaskMode.TRANSLATE_TO_ENGLISH && result.language != "en"
                val translated = if (shouldTranslate) {
                    mutableState.update {
                        it.copy(stage = Stage.TRANSLATING, progress = 0,
                            message = "Preparing the on-device text translation model…")
                    }
                    translateOriginal(result.segments, result.language)
                } else TranslationOutput(result.segments, "")
                mutableState.update {
                    it.copy(stage = Stage.DONE, progress = 100, segments = translated.segments,
                        resultIsTranslation = shouldTranslate,
                        translationProvider = translated.provider, message = "")
                }
            } catch (_: CancellationException) {
                mutableState.update {
                    if (it.originalSegments.isNotEmpty()) {
                        it.copy(stage = Stage.DONE, segments = it.originalSegments,
                            resultIsTranslation = false,
                            message = "Translation cancelled. Showing the original transcript.")
                    } else {
                        it.copy(stage = Stage.READY, message = "Processing cancelled.")
                    }
                }
            } catch (error: Exception) {
                mutableState.update {
                    if (cancelRequested) {
                        it.copy(stage = Stage.READY, message = "Processing cancelled.")
                    } else if (it.originalSegments.isNotEmpty()) {
                        it.copy(stage = Stage.DONE, segments = it.originalSegments,
                            resultIsTranslation = false,
                            message = "English translation failed: ${error.message?.trimEnd('.') ?: "unknown error"}. Showing the original transcript.")
                    } else {
                        it.copy(stage = Stage.ERROR, message = error.message ?: "Processing failed.")
                    }
                }
            } finally {
                activeJob = null
                cancelRequested = false
            }
        }
    }

    fun retryTranslation() {
        val current = mutableState.value
        if (busy() || current.mode != TaskMode.TRANSLATE_TO_ENGLISH ||
            current.originalSegments.isEmpty() || current.detectedLanguage == "en") return
        activeJob = viewModelScope.launch {
            mutableState.update { it.copy(stage = Stage.TRANSLATING, progress = 0,
                message = "Preparing the on-device text translation model…") }
            try {
                val translated = translateOriginal(current.originalSegments, current.detectedLanguage)
                mutableState.update { it.copy(stage = Stage.DONE, progress = 100,
                    segments = translated.segments, resultIsTranslation = true,
                    translationProvider = translated.provider, message = "") }
            } catch (_: CancellationException) {
                mutableState.update { it.copy(stage = Stage.DONE, segments = it.originalSegments,
                    resultIsTranslation = false, message = "Translation cancelled. Showing the original transcript.") }
            } catch (error: Exception) {
                mutableState.update { it.copy(stage = Stage.DONE, segments = it.originalSegments,
                    resultIsTranslation = false,
                    message = "English translation failed: ${error.message?.trimEnd('.') ?: "unknown error"}. Showing the original transcript.") }
            } finally {
                activeJob = null
            }
        }
    }

    private suspend fun translateOriginal(source: List<Segment>, language: String): TranslationOutput {
        val system = SystemTextTranslator.toEnglishIfAvailable(context, source, language,
            onReady = {
                mutableState.update { it.copy(message = "Translating with Android's offline language pack…") }
            },
            onChunk = { done, total ->
                mutableState.update { it.copy(progress = done * 100 / total) }
            },
        )
        if (system != null) return TranslationOutput(system, "Android system translator")
        return TranslationOutput(LocalTextTranslator.toEnglish(source, language,
            onModelReady = {
                mutableState.update { it.copy(message = "Translating the original transcript locally…") }
            },
            onChunk = { done, total ->
                mutableState.update { it.copy(progress = done * 100 / total) }
            },
        ), "Google Translate")
    }

    fun cancel() {
        if (!busy()) return
        cancelRequested = true
        bridge.cancel()
        activeJob?.cancel()
    }

    private fun busy(): Boolean = mutableState.value.stage in setOf(
        Stage.DOWNLOADING, Stage.PREPARING, Stage.PROCESSING, Stage.TRANSLATING,
    )
}

private data class TranslationOutput(val segments: List<Segment>, val provider: String)

data class LanguageOption(val code: String, val label: String)

val supportedLanguages = listOf(
    LanguageOption("auto", "Detect automatically"),
    LanguageOption("en", "English"),
    LanguageOption("es", "Spanish"),
    LanguageOption("tr", "Turkish"),
    LanguageOption("zh", "Chinese"),
    LanguageOption("ko", "Korean"),
    LanguageOption("pt", "Portuguese"),
    LanguageOption("fr", "French"),
    LanguageOption("de", "German"),
    LanguageOption("ar", "Arabic"),
    LanguageOption("hi", "Hindi"),
)
