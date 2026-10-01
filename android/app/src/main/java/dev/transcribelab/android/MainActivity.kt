package dev.transcribelab.android

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.Color

class MainActivity : ComponentActivity() {
    private val model: TranscribeViewModel by viewModels()

    private val pickAudio = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) model.select(uri)
    }

    private val saveText = registerForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { uri ->
        if (uri != null) {
            contentResolver.openOutputStream(uri)?.bufferedWriter(Charsets.UTF_8)?.use { writer ->
                writer.write(model.state.value.outputText)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        receiveSharedAudio(intent)
        setContent {
            val state by model.state.collectAsState()
            val working = state.stage == Stage.PREPARING || state.stage == Stage.PROCESSING
            DisposableEffect(working) {
                if (working) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                onDispose { window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }
            }
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Color(0xFFB9F34A),
                    onPrimary = Color(0xFF11130F),
                    background = Color(0xFF11130F),
                    surface = Color(0xFF1B1F19),
                    surfaceContainer = Color(0xFF1B1F19),
                    surfaceContainerHigh = Color(0xFF252A22),
                    secondary = Color(0xFFB9F34A),
                    onSurface = Color.White,
                ),
            ) {
                ResultFirstScreen(
                    state = state,
                    onPick = { pickAudio.launch(arrayOf("audio/*", "application/ogg", "application/octet-stream")) },
                    onDownload = model::downloadModel,
                    onMode = model::setMode,
                    onLanguage = model::setLanguage,
                    onModel = model::setModel,
                    onHint = model::setSpeechHint,
                    onFormat = model::setOutputFormat,
                    onRun = model::run,
                    onCancel = model::cancel,
                    onEditSegment = model::editSegment,
                    onCopy = ::copyResult,
                    onShare = ::shareResult,
                    onSave = ::saveResult,
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        receiveSharedAudio(intent)
    }

    private fun receiveSharedAudio(incoming: Intent?) {
        if (incoming?.action != Intent.ACTION_SEND) return
        @Suppress("DEPRECATION")
        val uri = if (Build.VERSION.SDK_INT >= 33) {
            incoming.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            incoming.getParcelableExtra(Intent.EXTRA_STREAM)
        } ?: incoming.clipData?.getItemAt(0)?.uri
        if (uri != null) model.select(uri)
    }

    private fun copyResult() {
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("Transcript", model.state.value.outputText))
    }

    private fun shareResult() {
        val result = model.state.value
        val share = Intent(Intent.ACTION_SEND).apply {
            type = if (result.outputFormat == OutputFormat.JSON) "application/json" else "text/plain"
            putExtra(Intent.EXTRA_TEXT, result.outputText)
        }
        startActivity(Intent.createChooser(share, "Share transcript"))
    }

    private fun saveResult() {
        val result = model.state.value
        val name = result.fileName?.substringBeforeLast('.') ?: "voice-note"
        val suffix = if (result.mode == TaskMode.TRANSLATE_TO_ENGLISH) "_english" else "_transcript"
        saveText.launch("$name$suffix.${result.outputFormat.extension}")
    }
}
