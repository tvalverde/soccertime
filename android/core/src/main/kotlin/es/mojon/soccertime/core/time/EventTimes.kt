package es.mojon.soccertime.core.time

import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale

/**
 * When an event is, in the reader's own terms.
 *
 * **This is a deliberate divergence from the website.** The site renders every event in
 * `Europe/Madrid` for everybody, which is right for a page whose readers are all watching
 * Spanish television. An app is carried, so it renders in the device's zone instead: a phone
 * in the Canaries shows 16:00 for the same kick-off the site calls 17:00, and shows it under
 * the day it falls on *there* — which for a late kick-off is the day before.
 *
 * Everything is injected. `Clock` and `ZoneId` are what make "is this on now" and "is this
 * today" testable at all, and the locale is fixed rather than read from the device because
 * every other string in these apps is Spanish with no translation behind it; taking day names
 * from `Locale.getDefault()` would produce "SATURDAY 30 AGOSTO" on an English phone.
 */
class EventTimes(
    private val clock: Clock = Clock.systemDefaultZone(),
    private val zone: ZoneId = ZoneId.systemDefault(),
    private val locale: Locale = SPAIN,
) {

    /**
     * Null rather than an exception. A date the parser cannot read is one row rendering
     * without its time, not a screen that fails to draw.
     */
    fun at(iso: String): ZonedDateTime? =
        try {
            OffsetDateTime.parse(iso).atZoneSameInstant(zone)
        } catch (e: DateTimeParseException) {
            null
        }

    fun instantAt(iso: String): Instant? = at(iso)?.toInstant()

    /** `17:00`, in the device's zone and always on a 24-hour clock, as the site shows it. */
    fun timeLabel(iso: String): String = at(iso)?.format(TIME) ?: ""

    /** The day the event falls on *here*, which is what listings group by. */
    fun dayOf(iso: String): LocalDate? = at(iso)?.toLocalDate()

    /**
     * `HOY`, `MAÑANA`, or `SÁBADO 30 AGOSTO`. Upper case because it is a section heading and
     * the design sets it in letter-spaced capitals; `Locale` matters here, since Turkish
     * would otherwise turn a dotted i into one nobody typed.
     */
    fun dayLabel(iso: String): String {
        val day = dayOf(iso) ?: return ""
        val today = LocalDate.now(clock.withZone(zone))
        return when (day) {
            today -> TODAY
            today.plusDays(1) -> TOMORROW
            else -> day.format(DAY.withLocale(locale)).uppercase(locale)
        }
    }

    /**
     * On right now.
     *
     * The end comes from the API when it has one. It always does today, and it is always
     * exactly two hours after the start, because `duration` is null on every row and the
     * serializer falls back to a flat default — so this behaves like the site's own
     * `live_state.js` while being ready for the day a real duration is stored.
     *
     * It errs towards silence, and that is the point: a cycling stage runs five hours and a
     * golf round all day, so a long event loses the badge while still running. Saying nothing
     * about something that is on is a smaller failure than claiming something is on when it
     * finished an hour ago, on a screen whose whole job is telling you what to watch.
     */
    fun isLive(startIso: String, endIso: String?): Boolean {
        val start = instantAt(startIso) ?: return false
        val end = endIso?.let(::instantAt) ?: start.plus(DEFAULT_LENGTH)
        val now = clock.instant()
        return !now.isBefore(start) && now.isBefore(end)
    }

    companion object {
        /** What the site assumes when no duration is stored, mirrored here. */
        val DEFAULT_LENGTH: Duration = Duration.ofHours(2)

        private val SPAIN = Locale.forLanguageTag("es-ES")
        private val TIME = DateTimeFormatter.ofPattern("HH:mm")
        private val DAY = DateTimeFormatter.ofPattern("EEEE d MMMM")
        private const val TODAY = "HOY"
        private const val TOMORROW = "MAÑANA"
    }
}
