package es.mojon.soccertime.core.ui

import es.mojon.soccertime.core.data.Favorites
import es.mojon.soccertime.core.data.FollowedItem
import es.mojon.soccertime.core.model.ChannelDto
import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.model.LinkDto
import es.mojon.soccertime.core.time.EventTimes
import java.time.Instant
import java.time.LocalDate

/**
 * What a row says, decided once for both applications.
 *
 * The phone and the television draw different things, but they say the same things: the same
 * time in the same zone, the same live window, the same two channels before a "+3". Deciding
 * that here is what stops the two screens disagreeing about the same event.
 */
class EventPresenter(val times: EventTimes) {

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

    /**
     * The event the listing should open on: the last one that has already started.
     *
     * Not the first that has not finished, which is the *oldest* thing still running and can
     * sit hours above the reader. And not the nearest in either direction either: at ten to
     * nine, with a match at seven and another at half past nine, the nearest is the one that
     * has not begun — and opening the agenda on something that is not on yet, with what *is*
     * on pushed above the fold, is the wrong way round. What has just started goes at the top
     * and everything to come reads downwards from it, which is how an agenda is read.
     *
     * One starting exactly now counts as started — the boundary is `start <= now`, not
     * `start < now`, so the event whose hour has just struck is the one you land on.
     *
     * Ordered by start and then by id so the answer does not depend on how the two halves of
     * the window were stitched together. When nothing has started — a window entirely ahead,
     * which the favourites screen is most of the time — it is the earliest, so the listing
     * opens at its top rather than nowhere.
     */
    fun anchor(events: List<EventDto>): Int? {
        val now = times.now()
        val dated = events
            .mapNotNull { event -> times.instantAt(event.date)?.let { Anchor(event.id, it) } }
            .sortedWith(compareBy({ it.start }, { it.id }))
        return (dated.lastOrNull { !it.start.isAfter(now) } ?: dated.firstOrNull())?.id
    }

    private data class Anchor(val id: Int, val start: Instant)

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

    /**
     * Everything that can be opened for one event, grouped the way the sheet draws it.
     *
     * Grouped by channel and then by quality because that is the shape of the problem: one
     * match carries fifteen links on `M+ LALIGA` and eight on `Movistar Plus+`, all of them
     * the same stream from different sources, and when one does not start the reader wants
     * the next of the same quality. Numbering is left to the view — it is the position in the
     * group, and it is what makes "the third one worked" a thing a person can say.
     */
    fun links(event: EventDto): EventLinks {
        val openable = event.channelsByAvailability.filter { it.openableLinks.isNotEmpty() }
        return EventLinks(
            title = if (event.isMatch) {
                listOfNotNull(event.local?.name, event.visitor?.name).joinToString(" — ")
            } else {
                (event.title ?: event.name).orEmpty()
            },
            time = times.timeLabel(event.date),
            live = times.isLive(event.date, event.dateEnd),
            competition = event.competition.name,
            home = event.local?.let { Side(it.name, it.crest?.url) },
            away = event.visitor?.let { Side(it.name, it.crest?.url) },
            channels = openable.map { channel ->
                ChannelLinks(
                    name = channel.name,
                    total = channel.openableLinks.size,
                    qualities = channel.openableLinks
                        .groupBy { it.quality.ifBlank { LinkDto.ANY_QUALITY } }
                        .toList()
                        .sortedBy { (quality, _) -> QUALITY_ORDER.indexOf(quality).takeIf { it >= 0 } ?: QUALITY_ORDER.size }
                        .map { (quality, links) -> QualityGroup(quality, links) },
                )
            },
            silent = event.channelsByAvailability
                .filter { it.openableLinks.isEmpty() }
                .map(ChannelDto::name),
        )
    }

    /**
     * What one event offers to follow: its two sides and its competition.
     *
     * A match names three things and a reader wanting "that team" has to say which — so the
     * choice is shown rather than guessed. A race or a simple event offers only its
     * competition, which is the whole reason competitions are followable at all.
     */
    fun followables(event: EventDto): List<Followable> = buildList {
        event.local?.let { add(Followable(FollowedItem(it.id, it.name, it.crest?.url), FollowableKind.Teams)) }
        event.visitor?.let { add(Followable(FollowedItem(it.id, it.name, it.crest?.url), FollowableKind.Teams)) }
        val competition = event.competition
        if (competition.id != 0 && competition.name.isNotBlank()) {
            add(
                Followable(
                    FollowedItem(competition.id, competition.name, competition.flag?.image?.url),
                    FollowableKind.Competitions,
                ),
            )
        }
    }

    private fun chip(channel: ChannelDto) =
        ChannelChip(name = channel.name, openable = channel.openableLinks.isNotEmpty())

    companion object {
        /** What fits beside the play button on a phone before the row starts truncating. */
        const val CHANNELS_SHOWN: Int = 2

        /** Best first. Anything the API invents later falls to the end rather than vanishing. */
        private val QUALITY_ORDER = listOf("FHD", "HD", "SD", LinkDto.ANY_QUALITY)
    }
}

data class AgendaDay(
    val date: LocalDate,
    val label: String,
    val events: List<EventUi>,
)

/**
 * Where the anchor sits among a listing's items, day headings counted.
 *
 * Both applications scroll a list whose items are headings interleaved with events, and both
 * were walking it themselves. An off-by-one here lands the reader on the wrong hour, which is
 * not a thing worth being wrong about in two places. Null when there is no anchor or it is not
 * on this listing.
 */
fun anchorPosition(anchorId: Int?, days: List<AgendaDay>): Int? {
    if (anchorId == null) return null
    var index = 0
    days.forEach { day ->
        index++
        day.events.forEach { event ->
            if (event.id == anchorId) return index
            index++
        }
    }
    return null
}

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

/** One event's openable links, and the channels that carry none. */
data class EventLinks(
    val title: String,
    val time: String,
    val live: Boolean,
    val competition: String,
    val home: Side?,
    val away: Side?,
    val channels: List<ChannelLinks>,
    val silent: List<String>,
) {
    val hasSomethingToOpen: Boolean get() = channels.isNotEmpty()
}

data class ChannelLinks(
    val name: String,
    val total: Int,
    val qualities: List<QualityGroup>,
)

data class QualityGroup(val quality: String, val links: List<LinkDto>)

/** Something an event offers to follow, and which of the two lists it belongs to. */
data class Followable(val item: FollowedItem, val kind: FollowableKind)
