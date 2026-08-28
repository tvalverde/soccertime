package es.mojon.soccertime.core.ui

import es.mojon.soccertime.core.data.Favorites
import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.model.Page
import es.mojon.soccertime.core.network.Network
import es.mojon.soccertime.core.time.EventTimes
import java.time.Clock
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Driven by the same recorded responses the parser tests use, so what a row says is checked
 * against events production actually served rather than against a shape invented here.
 */
class EventPresenterTest {

    private fun fixture(name: String): List<EventDto> {
        val body = checkNotNull(javaClass.classLoader?.getResourceAsStream("fixtures/$name"))
            .use { it.readBytes().decodeToString() }
        return Network.json.decodeFromString<Page<EventDto>>(body).results
    }

    private fun presenter(zone: String = "Europe/Madrid", now: String = "2026-08-30T12:00:00Z") =
        EventPresenter(
            EventTimes(
                clock = Clock.fixed(Instant.parse(now), ZoneId.of("UTC")),
                zone = ZoneId.of(zone),
            ),
        )

    @Test
    fun `a match names both sides and no title`() {
        val match = fixture("events_day_page1.json").first { it.eventType == "match" }

        val row = presenter().present(match)

        assertNull("a match is drawn from its two sides", row.title)
        assertNotNull(row.home)
        assertNotNull(row.away)
        assertTrue(row.competition.isNotEmpty())
        assertEquals(row.sport, row.sport.uppercase())
    }

    @Test
    fun `a race has a title and no sides`() {
        val race = fixture("events_watchable_page1.json").first { it.eventType == "race" }

        val row = presenter().present(race)

        assertNull(row.home)
        assertNull(row.away)
        assertTrue(row.title!!.isNotEmpty())
    }

    @Test
    fun `channels that can be opened are the ones shown first`() {
        val race = fixture("events_watchable_page1.json").first { it.eventType == "race" }

        val row = presenter().present(race)

        assertEquals(EventPresenter.CHANNELS_SHOWN, row.channels.size)
        assertTrue("the openable one leads", row.channels.first().openable)
        assertTrue("the rest are counted, not dropped", row.hiddenChannels > 0)
        assertTrue(row.openable)
    }

    @Test
    fun `an event nothing can open still says where it is on`() {
        val silent = fixture("events_day_page1.json").first { event ->
            event.channels.isNotEmpty() && event.channels.all { it.links.isEmpty() }
        }

        val row = presenter().present(silent)

        assertFalse("no play button", row.openable)
        assertTrue("but the channel is still named", row.channels.isNotEmpty())
        assertTrue(row.channels.none { it.openable })
    }

    @Test
    fun `the favourite mark is carried on the agenda and withheld where every row is one`() {
        val match = fixture("events_day_page1.json").first { it.eventType == "match" }
        val following = Favorites(teamIds = setOfNotNull(match.local?.id))

        assertTrue(presenter().present(match, following, markFavorites = true).favorite)
        assertFalse(presenter().present(match, following, markFavorites = false).favorite)
    }

    @Test
    fun `days are grouped where the reader is, not where the server is`() {
        val lateKickOff = fixture("events_day_page1.json").first()
            .copy(id = 1, date = "2026-08-31T00:30:00+02:00")

        val inMadrid = presenter("Europe/Madrid").days(listOf(lateKickOff))
        val inTheCanaries = presenter("Atlantic/Canary").days(listOf(lateKickOff))

        assertEquals(LocalDate.of(2026, 8, 31), inMadrid.single().date)
        assertEquals(LocalDate.of(2026, 8, 30), inTheCanaries.single().date)
    }

    @Test
    fun `days come out in order and keep every event`() {
        val events = fixture("events_day_page1.json")

        val days = presenter().days(events)

        assertEquals(events.size, days.sumOf { it.events.size })
        assertEquals(days.map { it.date }.sorted(), days.map { it.date })
        assertTrue(days.all { it.label.isNotEmpty() })
    }

    @Test
    fun `an event whose date cannot be read is left out rather than crashing the day`() {
        val events = fixture("events_day_page1.json")
        val broken = events.first().copy(id = 999_999, date = "not a date")

        val days = presenter().days(events + broken)

        assertEquals(events.size, days.sumOf { it.events.size })
        assertTrue(days.none { day -> day.events.any { it.id == 999_999 } })
    }

    @Test
    fun `live is decided against the injected clock, not the machine's`() {
        val match = fixture("events_day_page1.json").first()
            .copy(date = "2026-08-30T17:00:00+02:00", dateEnd = "2026-08-30T19:00:00+02:00")

        assertTrue(presenter(now = "2026-08-30T15:30:00Z").present(match).live)
        assertFalse(presenter(now = "2026-08-30T18:30:00Z").present(match).live)
    }

    @Test
    fun `the links of an event are grouped by channel and then by quality, best first`() {
        val race = fixture("events_watchable_page1.json").first { it.eventType == "race" }

        val links = presenter().links(race)

        assertTrue(links.hasSomethingToOpen)
        val channel = links.channels.first()
        assertEquals("nine links on one channel", 9, channel.total)
        assertEquals(channel.total, channel.qualities.sumOf { it.links.size })
        assertEquals(listOf("FHD", "HD", "SD", "ANY"), channel.qualities.map { it.quality })
        assertTrue("every link is openable", channel.qualities.all { group -> group.links.all { it.isOpenable } })
    }

    @Test
    fun `channels carrying nothing are listed apart rather than dropped`() {
        val race = fixture("events_watchable_page1.json").first { it.eventType == "race" }

        val links = presenter().links(race)

        assertTrue("the agenda still says where it is on", links.silent.isNotEmpty())
        assertTrue(links.silent.none { name -> links.channels.any { it.name == name } })
    }

    @Test
    fun `a quality the api invents later goes last instead of disappearing`() {
        val race = fixture("events_watchable_page1.json").first { it.eventType == "race" }
        val invented = race.copy(
            channels = race.channels.map { channel ->
                channel.copy(links = channel.links.map { it.copy(quality = "8K") })
            },
        )

        val links = presenter().links(invented)

        assertEquals(listOf("8K"), links.channels.first().qualities.map { it.quality })
        assertEquals(9, links.channels.first().total)
    }

    @Test
    fun `a match names both sides in the sheet header`() {
        val match = fixture("events_day_page1.json").first { it.eventType == "match" }

        val links = presenter().links(match)

        assertTrue(links.title.contains("—"))
        assertNotNull(links.home)
        assertNotNull(links.away)
    }
}