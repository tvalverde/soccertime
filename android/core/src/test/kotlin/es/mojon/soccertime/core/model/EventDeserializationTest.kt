package es.mojon.soccertime.core.model

import es.mojon.soccertime.core.network.Network
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The parser against responses the production API actually sent.
 *
 * Every fixture under `resources/fixtures` was recorded verbatim from
 * `https://www.mojon.es/soccertime/api/v1/` — the one exception is named where it is used.
 * Hand-written JSON would only ever assert that the model matches itself.
 */
class EventDeserializationTest {

    private val json = Network.json

    private fun fixture(name: String): String =
        checkNotNull(javaClass.classLoader?.getResourceAsStream("fixtures/$name")) {
            "missing fixture $name"
        }.use { it.readBytes().decodeToString() }

    private fun events(name: String): Page<EventDto> = json.decodeFromString(fixture(name))

    @Test
    fun `a page of matches carries its envelope and its rows`() {
        val page = events("events_day_page1.json")

        assertEquals(145, page.count)
        assertEquals(3, page.results.size)
        assertNotNull(page.next)
        assertNull(page.previous)
    }

    @Test
    fun `a match has both sides and a competition`() {
        val match = events("events_day_page1.json").results.first { it.eventType == "match" }

        assertTrue(match.isMatch)
        assertNotNull(match.local)
        assertNotNull(match.visitor)
        assertTrue(match.competition.name.isNotEmpty())
        assertTrue(match.competition.sport.name.isNotEmpty())
    }

    @Test
    fun `a race has no sides at all`() {
        val race = events("events_watchable_page1.json").results.first { it.eventType == "race" }

        assertFalse(race.isMatch)
        assertNull(race.local)
        assertNull(race.visitor)
        assertTrue(race.title != null || race.name != null)
    }

    @Test
    fun `a simple event has no sides either`() {
        val simple = events("events_simple_event.json").results.single()

        assertEquals("simple", simple.eventType)
        assertFalse(simple.isMatch)
        assertEquals("Etapa 9", simple.name)
    }

    @Test
    fun `a channel with no link is still a channel`() {
        val race = events("events_watchable_page1.json").results.first { it.eventType == "race" }
        val silent = race.channels.filter { it.links.isEmpty() }

        assertTrue("the fixture should carry channels with no links", silent.isNotEmpty())
        assertTrue(silent.all { it.openableLinks.isEmpty() })
    }

    @Test
    fun `openable links are the enabled playable ones that carry a url`() {
        val race = events("events_watchable_page1.json").results.first { it.eventType == "race" }
        val channel = race.channels.first { it.openableLinks.isNotEmpty() }

        assertTrue(channel.openableLinks.all { it.enabled })
        assertTrue(channel.openableLinks.all { it.playable })
        assertTrue(channel.openableLinks.all { !it.link.isNullOrBlank() })
        assertTrue(channel.openableLinks.all { it.scheme == "acestream" })
    }

    @Test
    fun `channels that can be opened come first`() {
        val race = events("events_watchable_page1.json").results.first { it.eventType == "race" }
        val ordered = race.channelsByAvailability

        val lastOpenable = ordered.indexOfLast { it.openableLinks.isNotEmpty() }
        val firstSilent = ordered.indexOfFirst { it.openableLinks.isEmpty() }
        assertTrue("a silent channel is ordered before an openable one", lastOpenable < firstSilent)
    }

    /**
     * `ChannelLink.link` is null whenever the stored URL uses a scheme the site refuses to
     * render, so this is the one fixture not recorded verbatim: the first hundred upcoming
     * events happened to carry none, and a state the API documents is not one to wait for.
     * Only that field is edited; everything around it is the recorded response.
     */
    @Test
    fun `a link the api withheld is parsed and never openable`() {
        val page = events("event_null_link.json")
        val links = page.results.flatMap { it.channels }.flatMap { it.links }
        val withheld = links.filter { it.link == null }

        assertTrue("the fixture should carry a withheld link", withheld.isNotEmpty())
        assertTrue(withheld.none { it.isOpenable })
        assertTrue("the rest of the page still parses", page.results.isNotEmpty())
    }

    @Test
    fun `a field the api adds later is ignored rather than fatal`() {
        val original = Json.parseToJsonElement(fixture("events_day_page1.json")).jsonObject
        val widened = widen(original)

        val page: Page<EventDto> = json.decodeFromString(widened.toString())

        assertEquals(original["count"]?.jsonPrimitive?.content?.toInt(), page.count)
        assertEquals(3, page.results.size)
    }

    /** Adds a key nothing knows about to the envelope and to every row inside it. */
    private fun widen(page: JsonObject): JsonObject {
        val rows = page["results"]!!.let { results ->
            kotlinx.serialization.json.JsonArray(
                results.let { it as kotlinx.serialization.json.JsonArray }.map { row ->
                    JsonObject(row.jsonObject + ("a_field_from_the_future" to json.parseToJsonElement("42")))
                },
            )
        }
        return JsonObject(page + ("results" to rows) + ("another_one" to json.parseToJsonElement("\"x\"")))
    }
}
