package dev.transcribelab.android

import java.util.Locale
import kotlin.math.roundToLong

enum class OutputFormat(val extension: String, val label: String) {
    TXT("txt", "TXT · readable text"),
    SRT("srt", "SRT · subtitles"),
    VTT("vtt", "VTT · web captions"),
    TSV("tsv", "TSV · timing data"),
    JSON("json", "JSON · segments"),
}

object TranscriptFormats {
    fun render(segments: List<Segment>, format: OutputFormat): String = when (format) {
        OutputFormat.TXT -> segments.joinToString("\n") { it.text.trim() }.trim() + "\n"
        OutputFormat.SRT -> segments.mapIndexed { index, segment ->
            "${index + 1}\n${timestamp(segment.startSeconds, ',')} --> " +
                "${timestamp(segment.endSeconds, ',')}\n${segment.text.trim()}"
        }.joinToString("\n\n", postfix = "\n")
        OutputFormat.VTT -> "WEBVTT\n\n" + segments.joinToString("\n\n", postfix = "\n") { segment ->
            "${timestamp(segment.startSeconds, '.')} --> " +
                "${timestamp(segment.endSeconds, '.')}\n${segment.text.trim()}"
        }
        OutputFormat.TSV -> "start\tend\ttext\n" + segments.joinToString("\n", postfix = "\n") { segment ->
            "${millis(segment.startSeconds)}\t${millis(segment.endSeconds)}\t" +
                segment.text.trim().replace(Regex("\\s+"), " ")
        }
        OutputFormat.JSON -> "{\n  \"segments\": [\n" + segments.joinToString(",\n") { segment ->
            "    {\"start\": ${decimal(segment.startSeconds)}, " +
                "\"end\": ${decimal(segment.endSeconds)}, \"text\": ${jsonString(segment.text.trim())}}"
        } + "\n  ]\n}\n"
    }

    fun shortTime(seconds: Float): String {
        val whole = seconds.toInt().coerceAtLeast(0)
        return String.format(Locale.US, "%02d:%02d", whole / 60, whole % 60)
    }

    private fun millis(seconds: Float) = (seconds * 1000).roundToLong().coerceAtLeast(0)

    private fun timestamp(seconds: Float, separator: Char): String {
        val milliseconds = millis(seconds)
        return String.format(
            Locale.US,
            "%02d:%02d:%02d%c%03d",
            milliseconds / 3_600_000,
            milliseconds / 60_000 % 60,
            milliseconds / 1_000 % 60,
            separator,
            milliseconds % 1_000,
        )
    }

    private fun decimal(value: Float) = String.format(Locale.US, "%.2f", value)

    private fun jsonString(value: String): String = buildString {
        append('"')
        value.forEach { character ->
            when (character) {
                '"' -> append("\\\"")
                '\\' -> append("\\\\")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> if (character.code < 0x20) {
                    append(String.format(Locale.US, "\\u%04x", character.code))
                } else {
                    append(character)
                }
            }
        }
        append('"')
    }
}
