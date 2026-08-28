package es.mojon.soccertime.core.ui

import es.mojon.soccertime.core.data.Favorites
import es.mojon.soccertime.core.model.ChannelDto
import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.time.EventTimes
import java.time.LocalDate

/**
 * What a row says, decided once for both applications.
 *
 * The phone and the television draw different things, but they say the same things: the same
 * time in the same zone, the same live window, the same two channels before a "+3". Deciding
 * that here is what stops the two screens disagreeing about the same event.
 */
class EventPresenter(private val times: EventTimes) {

    /**
     * Grouped into days, in the device's zone. Grouping has to happen after the conversion
     * and not before: the API orders by instant, and the day an instant falls on depends on
     * where the reader is — a 00:30 kick-off in Madrid belongs to the previous day further
     * west, and grouping on the server's day would file it under a heading it is not under.
     */
    fun days(
        events: List<EventDto>,
        favorites: Favorites = Favorites.NONE,
        markFavorites: Boolean = true,
    ): List<AgendaDay> =
        events
            .mapNotNull { event -> times.dayOf(event.date)?.let { it to event } }
            .groupBy({ it.first }, { it.second })
            .toSortedMap()
            .map { (day, ofThatDay) ->
                AgendaDay(
                    date = day,
                    label = times.dayLabel(ofThatDay.first().date),
                    events = ofThatDay.map { present(it, favorites, markFavorites) },
                )
            }

    fun present(
        event: EventDto,
        favorites: Favorites = Favorites.NONE,
        markFavorites: Boolean = true,
    ): EventUi {
        val ordered = event.channelsByAvailability
        return EventUi(
            id = event.id,
            time = times.timeLabel(event.date),
            live = times.isLive(event.date, event.dateEnd),
            /**
             * Never marked on a screen where every row is one already — the same rule the
             * site's own agenda item follows, and for the same reason: a mark every row
             * carries marks nothing.
             */
            favorite = markFavorites && favorites.covers(event),
            competition = event.competition.name,
            sport = event.competition.sport.name.uppercase(),
            flagUrl = event.competition.flag?.image?.url,
            title = if (event.isMatch) null else (event.title ?: event.name).orEmpty(),
            details = event.details?.takeIf { it.isNotBlank() },
            home = event.local?.let { Side(it.name, it.crest?.url) },
            away = event.visitor?.let { Side(it.name, it.crest?.url) },
            channels = ordered.take(CHANNELS_SHOWN).map(::chip),
            hiddenChannels = (ordered.size - CHANNELS_SHOWN).coerceAtLeast(0),
            openable = event.watchable && ordered.any { it.openableLinks.isNotEmpty() },
        )
    }

    private fun chip(channel: ChannelDto) =
        ChannelChip(name = channel.name, openable = channel.openableLinks.isNotEmpty())

    companion object {
        /** What fits beside the play button on a phone before the row starts truncating. */
        const val CHANNELS_SHOWN: Int = 2
    }
}

data class AgendaDay(
    val date: LocalDate,
    val label: String,
    val events: List<EventUi>,
)

data class EventUi(
    val id: Int,
    val time: String,
    val live: Boolean,
    val favorite: Boolean,
    val competition: String,
    val sport: String,
    val flagUrl: String?,
    /** Set for a race or a simple event, which have no two sides; null for a match. */
    val title: String?,
    val details: String?,
    val home: Side?,
    val away: Side?,
    val channels: List<ChannelChip>,
    val hiddenChannels: Int,
    /** Whether to draw the play button at all. */
    val openable: Boolean,
)

data class Side(val name: String, val crestUrl: String?)

/**
 * A channel that cannot be opened is still shown, muted. It carries the one fact a television
 * agenda exists to give — where the match is on — and the site learned that the hard way,
 * having once hidden it for 1,809 of 2,148 future events.
 */
data class ChannelChip(val name: String, val openable: Boolean)
