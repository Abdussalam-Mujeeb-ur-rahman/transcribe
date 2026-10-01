package dev.transcribelab.android

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TranscriptFormatsTest {
    private val segments = listOf(
        Segment(0f, 1.25f, " Hola "),
        Segment(2.5f, 3f, "mundo"),
    )

    @Test fun rendersReadableText() {
        assertEquals("Hola\nmundo\n", TranscriptFormats.render(segments, OutputFormat.TXT))
    }

    @Test fun rendersTimedSubtitles() {
        assertEquals(
            "1\n00:00:00,000 --> 00:00:01,250\nHola\n\n" +
                "2\n00:00:02,500 --> 00:00:03,000\nmundo\n",
            TranscriptFormats.render(segments, OutputFormat.SRT),
        )
        assertTrue(TranscriptFormats.render(segments, OutputFormat.VTT).startsWith("WEBVTT\n\n"))
    }

    @Test fun escapesJsonAndKeepsTiming() {
        val output = TranscriptFormats.render(
            listOf(Segment(0f, 1f, "He said \"hello\"\nagain")),
            OutputFormat.JSON,
        )
        assertTrue(output.contains("\"start\": 0.00"))
        assertTrue(output.contains("He said \\\"hello\\\"\\nagain"))
    }
}
