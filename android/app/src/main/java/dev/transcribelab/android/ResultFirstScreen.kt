package dev.transcribelab.android

import android.media.MediaPlayer
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.SaveAlt
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.foundation.Image
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import java.util.Locale

private val screenBackground = Color(0xFF11130F)
private val screenPanel = Color(0xFF1B1F19)
private val screenBorder = Color(0xFF343A31)
private val screenLime = Color(0xFFB9F34A)
private val screenAmber = Color(0xFFFFC45A)
private val screenMuted = Color(0xFFA6AEA0)

@Composable
fun ResultFirstScreen(
    state: ScreenState,
    onPick: () -> Unit,
    onDownload: () -> Unit,
    onMode: (TaskMode) -> Unit,
    onLanguage: (String) -> Unit,
    onModel: (ModelChoice) -> Unit,
    onHint: (String) -> Unit,
    onFormat: (OutputFormat) -> Unit,
    onRun: () -> Unit,
    onCancel: () -> Unit,
    onEditSegment: (Int, String) -> Unit,
    onCopy: () -> Unit,
    onShare: () -> Unit,
    onSave: () -> Unit,
) {
    val busy = state.stage in setOf(Stage.DOWNLOADING, Stage.PREPARING, Stage.PROCESSING)
    val done = state.stage == Stage.DONE
    var settingsExpanded by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf(false) }
    var elapsedSeconds by remember { mutableIntStateOf(0) }

    LaunchedEffect(state.stage) {
        if (state.stage != Stage.DONE) editing = false
        settingsExpanded = state.stage != Stage.DONE
    }
    LaunchedEffect(busy) {
        if (busy) {
            elapsedSeconds = 0
            while (true) {
                delay(1_000)
                elapsedSeconds++
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(screenBackground)
            .statusBarsPadding()
            .navigationBarsPadding(),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(start = 18.dp, end = 14.dp, top = 14.dp, bottom = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Image(
                    painter = painterResource(R.drawable.ic_launcher_foreground),
                    contentDescription = null,
                    modifier = Modifier.size(32.dp),
                )
                Text("TRANSCRIBE LAB", color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.Black)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Lock, contentDescription = null, tint = screenLime, modifier = Modifier.size(15.dp))
                Text(" LOCAL", color = screenLime, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                IconButton(onClick = { settingsExpanded = !settingsExpanded }) {
                    Icon(Icons.Default.MoreVert, contentDescription = "Open settings", tint = screenMuted)
                }
            }
        }

        Column(
            modifier = Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 18.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            FileBanner(
                fileName = state.fileName,
                done = done,
                busy = busy,
                onPick = onPick,
            )

            if (state.fileName != null) {
                Row(
                    modifier = Modifier.fillMaxWidth().background(screenPanel, androidx.compose.foundation.shape.RoundedCornerShape(24.dp))
                        .clickable(enabled = !busy) { settingsExpanded = !settingsExpanded }
                        .padding(horizontal = 18.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        if (state.mode == TaskMode.TRANSLATE_TO_ENGLISH) {
                            if (state.sourceLanguage == "auto") "Speech" else
                                supportedLanguages.first { it.code == state.sourceLanguage }.label
                        } else {
                            "Speech"
                        },
                        color = Color.White,
                        fontSize = 17.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        if (state.mode == TaskMode.TRANSLATE_TO_ENGLISH) "  →  English" else "  →  Text",
                        color = screenLime,
                        fontSize = 17.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(Modifier.weight(1f))
                    Icon(Icons.Default.ExpandMore, contentDescription = "Change mode and language", tint = screenMuted)
                }
                AudioPlayerBar(state.mediaUri)
            }

            if (!done || settingsExpanded) {
                SettingsPanel(
                    state = state,
                    busy = busy,
                    onMode = onMode,
                    onLanguage = onLanguage,
                    onModel = onModel,
                    onHint = onHint,
                    onFormat = onFormat,
                    onDownload = onDownload,
                )
            }

            if (busy && state.stage != Stage.DOWNLOADING) {
                Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                    SmallLabel("PROCESSING / ${shortTime(elapsedSeconds)} ELAPSED")
                    Text(
                        if (state.stage == Stage.PREPARING) "Preparing the recording…" else
                            if (state.progress > 0) "Speech processed: ${state.progress}%" else "Analyzing speech…",
                        color = Color.White,
                    )
                    if (state.progress > 0) {
                        LinearProgressIndicator(progress = { state.progress / 100f }, modifier = Modifier.fillMaxWidth())
                    } else {
                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    }
                    Text("Keep this app open while it processes.", color = screenMuted, fontSize = 12.sp)
                    OutlinedButton(onClick = onCancel) { Text("CANCEL") }
                }
            }

            if (state.message.isNotBlank()) {
                Text(state.message, color = if (state.stage == Stage.ERROR) screenAmber else screenMuted, fontSize = 13.sp)
            }

            if (done) {
                Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    SmallLabel(if (state.mode == TaskMode.TRANSLATE_TO_ENGLISH) "ENGLISH TRANSLATION" else "TRANSCRIPT")
                    Spacer(Modifier.weight(1f))
                    Text(
                        if (editing) "DONE EDITING" else "EDIT WORDS",
                        modifier = Modifier.clickable { editing = !editing }.padding(8.dp),
                        color = screenLime,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                    )
                }
                state.segments.forEachIndexed { index, segment ->
                    Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text(
                            "${TranscriptFormats.shortTime(segment.startSeconds)} – " +
                                TranscriptFormats.shortTime(segment.endSeconds),
                            color = screenAmber,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                        )
                        if (editing) {
                            OutlinedTextField(
                                value = segment.text,
                                onValueChange = { onEditSegment(index, it) },
                                modifier = Modifier.fillMaxWidth(),
                                minLines = 2,
                            )
                        } else {
                            Text(
                                segment.text.trim(),
                                color = Color.White,
                                fontSize = 22.sp,
                                lineHeight = 31.sp,
                            )
                        }
                        HorizontalDivider(color = screenBorder)
                    }
                }
                Text("Review names and important wording before sharing.", color = screenMuted, fontSize = 12.sp)
            } else if (state.fileName == null) {
                Text(
                    "Share a voice note from WhatsApp or choose a recording to begin.",
                    color = screenMuted,
                    fontSize = 17.sp,
                    lineHeight = 25.sp,
                )
            }
            Spacer(Modifier.height(4.dp))
        }

        if (done) {
            Column(
                modifier = Modifier.fillMaxWidth().background(screenBackground)
                    .padding(horizontal = 18.dp, vertical = 10.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth()
                        .background(screenPanel, androidx.compose.foundation.shape.RoundedCornerShape(15.dp))
                        .clickable { settingsExpanded = !settingsExpanded }
                        .padding(horizontal = 14.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(Icons.Default.Settings, contentDescription = null, tint = screenMuted,
                        modifier = Modifier.size(18.dp))
                    Text(
                        (if (state.mode == TaskMode.TRANSLATE_TO_ENGLISH) "Translate" else "Transcribe") + " · " +
                            supportedLanguages.first { it.code == state.sourceLanguage }.label + " · " +
                            state.outputFormat.extension.uppercase(Locale.US),
                        color = Color.White,
                        fontSize = 13.sp,
                        modifier = Modifier.weight(1f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Icon(Icons.Default.ExpandMore, contentDescription = "Show settings", tint = screenMuted)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    Button(
                        onClick = onCopy,
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(containerColor = screenLime, contentColor = screenBackground),
                    ) {
                        Icon(Icons.Default.ContentCopy, contentDescription = null, modifier = Modifier.size(17.dp))
                        Text(" Copy", fontWeight = FontWeight.Bold)
                    }
                    OutlinedButton(onClick = onShare, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(17.dp))
                        Text(" Share")
                    }
                    OutlinedButton(onClick = onSave, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Default.SaveAlt, contentDescription = null, modifier = Modifier.size(17.dp))
                        Text(" Save")
                    }
                }
                OutlinedButton(onClick = onPick, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                    Text(" Transcribe New Voice Note")
                }
            }
        } else {
            Column(
                modifier = Modifier.fillMaxWidth().background(screenBackground).padding(horizontal = 18.dp, vertical = 10.dp),
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                Button(
                    onClick = onRun,
                    enabled = state.fileName != null && state.modelReady && !busy,
                    modifier = Modifier.fillMaxWidth().height(54.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = screenLime, contentColor = screenBackground),
                ) {
                    if (busy) CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    else Text(
                        if (state.mode == TaskMode.TRANSCRIBE) "TRANSCRIBE SPEECH" else "TRANSLATE TO ENGLISH",
                        fontWeight = FontWeight.Black,
                    )
                }
                Text(
                    "Audio stays on your phone. Internet is used only to download a model.",
                    color = screenMuted,
                    fontSize = 10.sp,
                )
            }
        }
    }
}

@Composable
private fun FileBanner(fileName: String?, done: Boolean, busy: Boolean, onPick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth()
            .background(screenPanel, androidx.compose.foundation.shape.RoundedCornerShape(16.dp))
            .clickable(enabled = !busy) { onPick() }
            .padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Icon(
            if (fileName == null) Icons.Default.FolderOpen else Icons.Default.Description,
            contentDescription = null,
            tint = Color.White,
            modifier = Modifier.size(26.dp),
        )
        Column(modifier = Modifier.weight(1f)) {
            Text(
                fileName ?: "Choose a voice note",
                color = Color.White,
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(if (fileName == null) "Tap to import audio" else "Tap to choose another recording",
                color = screenMuted, fontSize = 12.sp)
        }
        if (done) Icon(Icons.Default.CheckCircle, contentDescription = "Transcribed", tint = screenLime)
    }
}

@Composable
private fun AudioPlayerBar(uri: Uri?) {
    val context = LocalContext.current
    val player = remember(uri) {
        if (uri == null) null else try {
            MediaPlayer.create(context, uri)
        } catch (_: Exception) {
            null
        }
    }
    var playing by remember(uri) { mutableStateOf(false) }
    var positionMs by remember(uri) { mutableIntStateOf(0) }
    DisposableEffect(player) {
        player?.setOnCompletionListener { playing = false; positionMs = 0 }
        onDispose {
            player?.setOnCompletionListener(null)
            player?.release()
        }
    }
    LaunchedEffect(player, playing) {
        while (playing && player != null) {
            positionMs = player.currentPosition
            delay(250)
        }
    }
    if (player == null) return
    val durationMs = player.duration.coerceAtLeast(1)
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        IconButton(onClick = {
            if (playing) player.pause() else player.start()
            playing = !playing
        }, modifier = Modifier.background(screenLime, androidx.compose.foundation.shape.CircleShape).size(42.dp)) {
            Icon(if (playing) Icons.Default.Pause else Icons.Default.PlayArrow,
                contentDescription = if (playing) "Pause audio" else "Play audio", tint = screenBackground)
        }
        Text(shortTime(positionMs / 1000), color = screenMuted, fontSize = 12.sp)
        Slider(
            value = positionMs.coerceIn(0, durationMs).toFloat(),
            onValueChange = {
                positionMs = it.toInt()
                player.seekTo(positionMs)
            },
            valueRange = 0f..durationMs.toFloat(),
            colors = SliderDefaults.colors(
                thumbColor = screenLime,
                activeTrackColor = screenLime,
                inactiveTrackColor = screenBorder,
                activeTickColor = screenLime,
                inactiveTickColor = screenBorder,
            ),
            modifier = Modifier.weight(1f),
        )
        Text(shortTime(durationMs / 1000), color = screenMuted, fontSize = 12.sp)
    }
}

@Composable
private fun SettingsPanel(
    state: ScreenState,
    busy: Boolean,
    onMode: (TaskMode) -> Unit,
    onLanguage: (String) -> Unit,
    onModel: (ModelChoice) -> Unit,
    onHint: (String) -> Unit,
    onFormat: (OutputFormat) -> Unit,
    onDownload: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxWidth()
            .background(screenPanel, androidx.compose.foundation.shape.RoundedCornerShape(16.dp))
            .padding(15.dp),
        verticalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Settings, contentDescription = null, tint = screenAmber, modifier = Modifier.size(18.dp))
            Text("  SETTINGS", color = screenAmber, fontFamily = FontFamily.Monospace,
                fontSize = 12.sp, fontWeight = FontWeight.Bold)
        }
        MenuSetting(
            label = "MODE",
            value = if (state.mode == TaskMode.TRANSCRIBE) "Transcribe · original language" else "Translate · into English",
            options = TaskMode.entries.map {
                it to if (it == TaskMode.TRANSCRIBE) "Transcribe in spoken language" else "Translate into English"
            },
            enabled = !busy,
            onSelect = onMode,
        )
        MenuSetting(
            label = "SPOKEN LANGUAGE",
            value = supportedLanguages.first { it.code == state.sourceLanguage }.label,
            options = supportedLanguages.map { it.code to it.label },
            enabled = !busy,
            onSelect = onLanguage,
        )
        MenuSetting(
            label = "OUTPUT FORMAT",
            value = state.outputFormat.label,
            options = OutputFormat.entries.map { it to it.label },
            enabled = !busy,
            onSelect = onFormat,
        )
        MenuSetting(
            label = "ON-DEVICE MODEL",
            value = state.modelChoice.displayName,
            options = ModelChoice.entries.map { it to "${it.displayName} · ${it.downloadMiB} MB" },
            enabled = !busy,
            onSelect = onModel,
        )
        if (!state.modelReady) {
            Text("One download of about ${state.modelChoice.downloadMiB} MB is needed.",
                color = screenMuted, fontSize = 12.sp)
            if (state.stage == Stage.DOWNLOADING) {
                if (state.modelProgress > 0) {
                    LinearProgressIndicator(progress = { state.modelProgress / 100f }, modifier = Modifier.fillMaxWidth())
                } else {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
                Text("Downloading ${state.modelProgress}%", color = screenMuted, fontSize = 12.sp)
            } else {
                OutlinedButton(onClick = onDownload, modifier = Modifier.fillMaxWidth()) {
                    Text("DOWNLOAD ${state.modelChoice.name} MODEL")
                }
            }
        }
        OutlinedTextField(
            value = state.speechHint,
            onValueChange = onHint,
            enabled = !busy,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Names or terms to listen for · optional") },
            maxLines = 2,
        )
        Text("Hints may help with names, but cannot guarantee exact words.", color = screenMuted, fontSize = 11.sp)
    }
}

@Composable
private fun <T> MenuSetting(
    label: String,
    value: String,
    options: List<Pair<T, String>>,
    enabled: Boolean,
    onSelect: (T) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    Column {
        Text(label, color = screenMuted, fontFamily = FontFamily.Monospace, fontSize = 10.sp)
        Row(
            modifier = Modifier.fillMaxWidth().clickable(enabled = enabled) { expanded = true }
                .padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(value, color = Color.White, fontSize = 15.sp, modifier = Modifier.weight(1f))
            Icon(Icons.Default.ExpandMore, contentDescription = "Choose $label", tint = screenLime)
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { (option, title) ->
                DropdownMenuItem(text = { Text(title) }, onClick = {
                    onSelect(option)
                    expanded = false
                })
            }
        }
        HorizontalDivider(color = screenBorder)
    }
}

@Composable
private fun SmallLabel(text: String) {
    Text(text, color = screenAmber, fontSize = 12.sp, fontWeight = FontWeight.Bold,
        fontFamily = FontFamily.Monospace, letterSpacing = 0.8.sp)
}

private fun shortTime(seconds: Int): String =
    String.format(Locale.US, "%02d:%02d", seconds / 60, seconds % 60)
