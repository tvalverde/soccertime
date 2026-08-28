package es.mojon.soccertime.core.time

import java.time.Clock
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The apps show the device's own time, which the website deliberately does not, so these are
 * the tests that say what that actually costs and buys. Every one of them fixes both the
 * clock and the zone: a test that read either from the machine would pass in Madrid in
 * August and nowhere else.
 */
class EventTimesTest {

    /** Real, from the API: `Real Madrid - Málaga`, La Liga, on a Saturday in August. */
    private val kickOff = "2026-08-30T17:00:00+02:00"
    private val kickOffEnd = "2026-08-30T19:00:00+02:00"

    private fun at(zone: String, now: String = "2026-08-30T12:00:00Z") =
        EventTimes(
            clock = Clock.fixed(Instant.parse(now), ZoneId.of("UTC")),
            zone = ZoneId.of(zone),
        )

    @Test
    fun `one instant is one instant, whatever the device calls it`() {
        val zones = listOf("Europe/Madrid", "Atlantic/Canary", "UTC", "America/New_York")
        val instants = zones.map { at(it).instantAt(kickOff) }

        assertEquals(1, instants.toSet().size)
        assertEquals(Instant.parse("2026-08-30T15:00:00Z"), instants.first())
    }

    @Test
    fun `the time on screen is the time where the reader is`() {
        assertEquals("17:00", at("Europe/Madrid").timeLabel(kickOff))
        assertEquals("16:00", at("Atlantic/Canary").timeLabel(kickOff))
        assertEquals("15:00", at("UTC").timeLabel(kickOff))
        assertEquals("11:00", at("America/New_York").timeLabel(kickOff))
    }

    @Test
    fun `a late kick off belongs to a different day further west`() {
        // 00:30 in Madrid on the 31st is 23:30 on the 30th in the Canaries, and the listing
        // groups by the day it falls on *here* — the visible cost of showing local time.
        val lateKickOff = "2026-08-31T00:30:00+02:00"

        assertEquals(LocalDate.of(2026, 8, 31), at("Europe/Madrid").dayOf(lateKickOff))
        assertEquals(LocalDate.of(2026, 8, 30), at("Atlantic/Canary").dayOf(lateKickOff))
        assertEquals(LocalDate.of(2026, 8, 30), at("America/New_York").dayOf(lateKickOff))
    }

    @Test
    fun `the day heading names the day and then dates it`() {
        val times = at("Europe/Madrid", now = "2026-08-30T12:00:00Z")

        assertEquals("AYER · SÁB 29 AGO", times.dayLabel("2026-08-29T21:00:00+02:00"))
        assertEquals("HOY · DOM 30 AGO", times.dayLabel(kickOff))
        assertEquals("MAÑANA · LUN 31 AGO", times.dayLabel("2026-08-31T21:30:00+02:00"))
        assertEquals("MARTES 1 SEPTIEMBRE", times.dayLabel("2026-09-01T21:00:00+02:00"))
    }

    /**
     * The listing spans two days, so the heading is what tells a reader which side of midnight
     * a row is on. A bare `HOY` would say nothing about the row above it.
     */
    @Test
    fun `a named day carries its date so two of them can be told apart`() {
        val times = at("Europe/Madrid", now = "2026-08-30T12:00:00Z")

        val yesterday = times.dayLabel("2026-08-29T21:00:00+02:00")
        val today = times.dayLabel(kickOff)

        assertTrue(yesterday.startsWith("AYER"))
        assertTrue(today.startsWith("HOY"))
        assertTrue(yesterday.contains("29"))
        assertTrue(today.contains("30"))
    }

    @Test
    fun `today is decided in the device's zone and not the server's`() {
        // 01:30 in Madrid is still the previous evening in London, so the same event sits
        // under a different heading depending on where the phone is.
        val lateKickOff = "2026-08-31T01:30:00+02:00"
        val now = "2026-08-30T20:00:00Z"

        assertTrue(at("Europe/Madrid", now).dayLabel(lateKickOff).startsWith("MAÑANA"))
        assertTrue(at("UTC", now).dayLabel(lateKickOff).startsWith("HOY"))
    }

    @Test
    fun `the clocks going back does not move an event`() {
        // Spain leaves summer time at 03:00 on 2026-10-25. An event stored with the winter
        // offset must still read as the wall-clock time it was published as.
        val afterTheChange = "2026-10-25T17:00:00+01:00"

        assertEquals("17:00", at("Europe/Madrid").timeLabel(afterTheChange))
        assertEquals("16:00", at("UTC").timeLabel(afterTheChange))
    }

    @Test
    fun `an event is live from the moment it starts until it ends`() {
        fun liveAt(now: String) = at("Europe/Madrid", now).isLive(kickOff, kickOffEnd)

        assertFalse("a minute early", liveAt("2026-08-30T14:59:00Z"))
        assertTrue("at kick-off", liveAt("2026-08-30T15:00:00Z"))
        assertTrue("half-time", liveAt("2026-08-30T15:45:00Z"))
        assertFalse("at the final whistle the window is closed", liveAt("2026-08-30T17:00:00Z"))
        assertFalse("an hour later", liveAt("2026-08-30T18:00:00Z"))
    }

    @Test
    fun `an event with no end falls back to the same two hours the site assumes`() {
        fun liveAt(now: String) = at("Europe/Madrid", now).isLive(kickOff, null)

        assertTrue(liveAt("2026-08-30T16:59:00Z"))
        assertFalse(liveAt("2026-08-30T17:00:00Z"))
    }

    @Test
    fun `the answer does not depend on where the reader is standing`() {
        val zones = listOf("Europe/Madrid", "Atlantic/Canary", "UTC", "America/New_York")
        val answers = zones.map { at(it, now = "2026-08-30T15:45:00Z").isLive(kickOff, kickOffEnd) }

        assertEquals(setOf(true), answers.toSet())
    }

    @Test
    fun `a date the parser cannot read costs one row, not the screen`() {
        val times = at("Europe/Madrid")

        assertNull(times.at("not a date"))
        assertNull(times.dayOf(""))
        assertEquals("", times.timeLabel("2026-08-30 17:00:00"))
        assertEquals("", times.dayLabel("nope"))
        assertFalse(times.isLive("nope", null))
    }
}
