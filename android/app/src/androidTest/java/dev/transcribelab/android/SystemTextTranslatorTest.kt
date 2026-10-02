package dev.transcribelab.android

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class SystemTextTranslatorTest {
    @Test fun spanishToEnglishWithInstalledLanguagePack() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val result = SystemTextTranslator.toEnglishIfAvailable(
            context, listOf(Segment(0f, 3f, "Muchísimas gracias, buen día.")), "es",
            onReady = {}, onChunk = { _, _ -> },
        )
        assumeTrue("Requires an installed Spanish-English system pack", result != null)
        assertTrue(result!!.first().text.contains("thank", ignoreCase = true))
    }
}
