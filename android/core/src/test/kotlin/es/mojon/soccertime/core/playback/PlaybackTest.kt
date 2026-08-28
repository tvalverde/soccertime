package es.mojon.soccertime.core.playback

import es.mojon.soccertime.core.model.LinkDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the app does with a link, and — as much — what it refuses to do: look at what is
 * installed before trying.
 */
class PlaybackTest {

    /** Real, from the API: one of the fifteen links on `M+ LALIGA (M54 O110)`. */
    private val aceStream = LinkDto(
        id = 1,
        quality = "FHD",
        link = "acestream://3ce95bc9d6fc63676d828bb2cfc7a1f1854fd259",
        scheme = "acestream",
        playable = true,
        enabled = true,
    )

    private class Recorder(private val answers: Boolean = true) : IntentLauncher {
        val attempts = mutableListOf<String>()

        override fun launch(url: String) {
            attempts += url
            if (!answers) throw NoHandlerException()
        }
    }

    @Test
    fun `the url reaches the system exactly as the api sent it`() {
        val launcher = Recorder()

        val result = Playback(launcher).open(aceStream)

        assertEquals(listOf(aceStream.link), launcher.attempts)
        assertEquals(PlayResult.Launched(aceStream.link!!), result)
    }

    @Test
    fun `nothing answering is reported with the scheme, not treated as a crash`() {
        val result = Playback(Recorder(answers = false)).open(aceStream)

        assertEquals(PlayResult.NoHandler("acestream", aceStream.link!!), result)
    }

    @Test
    fun `it tries before it concludes anything about the device`() {
        // The whole point: no probe, no `<queries>`, no installed-package check. The only way
        // this app learns that nothing handles a scheme is by asking the system to open it.
        val launcher = Recorder(answers = false)

        Playback(launcher).open(aceStream)

        assertEquals("the launch was attempted", 1, launcher.attempts.size)
    }

    @Test
    fun `every scheme the api allows is handed over the same way`() {
        val launcher = Recorder()
        val playback = Playback(launcher)
        val schemes = listOf("http", "https", "ftp", "ftps", "acestream", "sop", "rtmp", "m3u8")

        schemes.forEach { scheme ->
            playback.open(aceStream.copy(scheme = scheme, link = "$scheme://somewhere/stream"))
        }

        assertEquals(schemes.map { "$it://somewhere/stream" }, launcher.attempts)
    }

    @Test
    fun `a link the api withheld is never handed to the system`() {
        val launcher = Recorder()

        val result = Playback(launcher).open(
            aceStream.copy(link = null, scheme = "magnet", playable = false),
        )

        assertEquals(PlayResult.Withheld, result)
        assertTrue("nothing was attempted", launcher.attempts.isEmpty())
    }

    @Test
    fun `a disabled link is not opened either`() {
        val launcher = Recorder()

        val result = Playback(launcher).open(aceStream.copy(enabled = false))

        assertEquals(PlayResult.Withheld, result)
        assertTrue(launcher.attempts.isEmpty())
    }

    @Test
    fun `a scheme the api left blank is recovered from the url`() {
        val result = Playback(Recorder(answers = false)).open(aceStream.copy(scheme = ""))

        assertEquals("acestream", (result as PlayResult.NoHandler).scheme)
    }
}
