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

enum class Stage { CHECKING, READY, DOWNLOADING, PREPARING, PROCESSING, DONE, ERROR }
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
            mutableState.update { it.copy(stage = Stage.PREPARING, progress = 0, message = "", segments = emptyList()) }
            try {
                val samples = AudioPipeline.decode(context, uri)
                val model = ModelStore.modelFile(context, settings.modelChoice)
                mutableState.update { it.copy(stage = Stage.PROCESSING) }
                val segments = withContext(Dispatchers.Default) {
                    bridge.process(
                        model.absolutePath,
                        samples,
                        settings.sourceLanguage,
                        settings.mode == TaskMode.TRANSLATE_TO_ENGLISH,
                        settings.speechHint.trim(),
                    ) { percent ->
                        mutableState.update { it.copy(progress = percent) }
                    }
                }
                check(segments.any { it.text.isNotBlank() }) { "No speech was detected in this recording." }
                mutableState.update {
                    it.copy(stage = Stage.DONE, progress = 100, segments = segments)
                }
            } catch (_: CancellationException) {
                mutableState.update { it.copy(stage = Stage.READY, message = "Processing cancelled.") }
            } catch (error: Exception) {
                mutableState.update {
                    if (cancelRequested) {
                        it.copy(stage = Stage.READY, message = "Processing cancelled.")
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

    fun cancel() {
        if (!busy()) return
        cancelRequested = true
        bridge.cancel()
        activeJob?.cancel()
    }

    private fun busy(): Boolean = mutableState.value.stage in setOf(
        Stage.DOWNLOADING, Stage.PREPARING, Stage.PROCESSING,
    )
}

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
