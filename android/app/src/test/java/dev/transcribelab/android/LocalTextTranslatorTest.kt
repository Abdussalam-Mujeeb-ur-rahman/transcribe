package dev.transcribelab.android

import org.junit.Assert.assertEquals
import org.junit.Test

class LocalTextTranslatorTest {
    @Test fun combinesSpeechAcrossWhisperSegmentsUntilSentenceEnd() {
        val chunks = sentenceChunks(listOf(
            Segment(0f, 2f, "Sí, nosotros pues tenemos"),
            Segment(2f, 4f, "la página."),
            Segment(4f, 6f, "También tenemos Instagram."),
        ))
        assertEquals(listOf(
            Segment(0f, 4f, "Sí, nosotros pues tenemos la página."),
            Segment(4f, 6f, "También tenemos Instagram."),
        ), chunks)
    }

    @Test fun retainsTrailingUnpunctuatedSpeech() {
        assertEquals(
            listOf(Segment(1f, 3f, "buen día a todos")),
            sentenceChunks(listOf(Segment(1f, 2f, "buen día"), Segment(2f, 3f, "a todos"))),
        )
    }
}
