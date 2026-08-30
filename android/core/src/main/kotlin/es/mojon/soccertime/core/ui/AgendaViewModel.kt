package es.mojon.soccertime.core.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import es.mojon.soccertime.core.data.AgendaQuery
import es.mojon.soccertime.core.data.EventsRepository
import es.mojon.soccertime.core.data.Favorites
import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.network.ApiError
import es.mojon.soccertime.core.network.ApiResult
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/**
 * The agenda: yesterday and today, optionally narrowed by a search, by a followed team or
 * competition, and by whether anything can be opened.
 *
 * The window is two days because midnight is not a boundary the reader observes. At 00:20 the
 * match that kicked off at 23:00 is still on, and a listing that began at the stroke of the
 * hour would have nothing to show. A calendar can narrow the listing to any single day
 * instead: a chosen day is one request rather than two, because "the evening before it" is a
 * courtesy the present deserves and an arbitrary Tuesday does not.
 *
 * Two days do not fit in one request — a hundred is the largest page the API serves and two
 * days regularly exceed it — so it is two, and their order is the design: **today first**.
 * Today is where the reader is, it is what positions the list, and it renders while yesterday
 * is still in flight. Yesterday arrives second, is asked for newest-first so a busy day keeps
 * the hours next to midnight, and is prepended. A failure there costs the tail of the window
 * and leaves today standing.
 *
 * The whole shape of this class is the rate limit. Thirty requests a minute are counted per
 * address, which means shared by every device in the house and by a browser open on the same
 * connection — so the interesting decisions here are all about *not* asking:
 *
 *  - typing is debounced, and a query under two characters is treated as no query at all,
 *    because "R" narrows nothing and costs a request across six joined tables;
 *  - a page holds a hundred, the largest the API allows, so a whole day is one request and
 *    a busy one is two;
 *  - a manual refresh inside five seconds of the last load does nothing, because the answer
 *    cannot have changed and the gesture is easy to repeat by accident;
 *  - returning to the screen reloads only if what is on it is over a minute old.
 *
 * When a load fails and the query has not moved, the last good answer stays on screen with a
 * banner rather than being replaced by an error page: an agenda a minute out of date is worth
 * more than no agenda, and this is a screen people open to find out what is on right now.
 */
@OptIn(ExperimentalCoroutinesApi::class, FlowPreview::class)
class AgendaViewModel(
    private val events: EventsRepository,
    private val presenter: EventPresenter,
    private val clock: Clock = Clock.systemUTC(),
    favorites: Flow<Favorites> = flowOf(Favorites.NONE),
) : ViewModel() {

    /**
     * Bumped to ask for the window again. A refresh goes through the same pipeline as every
     * other load rather than launching one of its own: on its own it reloaded whatever was
     * last loaded, which after moving from one followed thing to another is the one that was
     * left behind — fetched alongside the new one, and its yesterday prepended onto it.
     */
    private val reloads = MutableStateFlow(0)

    private val search = MutableStateFlow("")
    private val filters = MutableStateFlow(Filters(watchableOnly = false, narrowing = null, day = null))
    private val state = MutableStateFlow(AgendaUiState(day = today()))

    val uiState: StateFlow<AgendaUiState> = state.asStateFlow()

    private var loadedAt: Instant? = null
    private var loaded: List<EventDto> = emptyList()
    private var loadedFor: Query? = null
    private var nextPage: Int? = null
    private var marked: Favorites = Favorites.NONE

    /**
     * The last day the listing reaches. Appending pages walks this day; "load tomorrow"
     * starts the day after it. Advanced only when a fetch for a day succeeds, so a pull whose
     * request never came back leaves the foot naming the same day it named before.
     */
    private var windowEnd: LocalDate? = null

    /** One day-append at a time: the same day arriving twice is a duplicate-key crash. */
    private var appendingDay = false

    /** Which load owns the screen. An older one that answers late is no longer entitled to. */
    private var generation = 0

    /**
     * Whether a load that will replace the whole listing is in the air.
     *
     * While one is, `loadedFor` and `nextPage` still describe the listing being thrown away,
     * so its next page is a page of nothing the reader is looking at. Asking for it and
     * appending the answer put an event from the plain agenda inside a followed team's.
     */
    private var replacing = false

    init {
        viewModelScope.launch {
            combine(
                search.debounce { if (it.isEmpty()) 0L else TYPING_PAUSE_MILLIS }
                    .map(::effectiveSearch)
                    .distinctUntilChanged(),
                filters,
                reloads,
            ) { text, applied, _ -> Query(text, applied.watchableOnly, applied.narrowing, day = applied.day) }
                // collectLatest, so a query that arrives while an older one is still in
                // flight cancels it rather than queueing behind it.
                .collectLatest { load(it, appending = false) }
        }

        // Separately, and deliberately not part of the query above: following a team changes
        // which rows carry the mark and nothing about which rows the server would return, so
        // it re-draws what is already here rather than costing a request.
        viewModelScope.launch {
            favorites.collect { current ->
                marked = current
                if (loaded.isNotEmpty()) {
                    state.value = state.value.copy(days = presenter.days(loaded, current))
                }
            }
        }
    }

    fun onIntent(intent: AgendaIntent) {
        when (intent) {
            is AgendaIntent.Search -> {
                search.value = intent.text
                state.value = state.value.copy(query = intent.text)
            }
            is AgendaIntent.Narrow -> {
                // Only when it really moves. Both apps re-send the filter every time the
                // agenda re-enters composition; the `StateFlow` turns a repeat into no reload,
                // but the clearing below would blank a screen already showing the answer.
                if (intent.filter == filters.value.narrowing) return
                filters.value = filters.value.copy(narrowing = intent.filter)
                forgetListing()
                state.value = state.value.copy(
                    filter = intent.filter,
                    nextDayLabel = null,
                    days = emptyList(),
                    anchorId = null,
                    count = 0,
                    canLoadMore = false,
                    // Said out loud rather than left blank: the answer is seconds away and an
                    // empty screen with no explanation reads as an app that has broken.
                    loading = true,
                    // The banner belongs to the listing being left. Kept, it would sit over
                    // the "Cargando" of a listing that has not failed at all.
                    error = null,
                    showingStale = false,
                )
            }
            is AgendaIntent.OnlyWatchable -> {
                filters.value = filters.value.copy(watchableOnly = intent.only)
                state.value = state.value.copy(watchableOnly = intent.only)
            }
            is AgendaIntent.PickDay -> {
                if (intent.day == filters.value.day) return
                filters.value = filters.value.copy(day = intent.day)
                forgetListing()
                // The same clearing `Narrow` does, and for the same reasons: the rows on
                // screen belong to a window the reader has just left.
                state.value = state.value.copy(
                    chosenDay = intent.day,
                    nextDayLabel = null,
                    days = emptyList(),
                    anchorId = null,
                    count = 0,
                    canLoadMore = false,
                    loading = true,
                    error = null,
                    showingStale = false,
                )
            }
            AgendaIntent.Refresh -> refresh(minimumAge = MANUAL_REFRESH_INTERVAL)
            AgendaIntent.Resumed -> refresh(minimumAge = STALE_AFTER)
            AgendaIntent.LoadMore -> loadMore()
            AgendaIntent.LoadNextDay -> loadNextDay()
            AgendaIntent.DismissError -> state.value = state.value.copy(error = null)
        }
    }

    /**
     * Today, where the reader is, asked afresh for every load.
     *
     * Held once, it was whatever day the view model happened to be built on. A television is
     * left composed for days at a time, so the morning after, the agenda would still be
     * fetching the window it was born with — under headings naming a date that had moved on.
     * Taken from the presenter, which is the only thing here that knows where the reader is.
     */
    private fun today(): LocalDate = presenter.times.today()

    /** The two sides and the competition of one row, for the panel that follows them. */
    fun followablesFor(id: Int): List<Followable> =
        loaded.firstOrNull { it.id == id }?.let(presenter::followables).orEmpty()

    /** The links of one row, built from the response the row was drawn from. */
    fun linksFor(id: Int): EventLinks? = loaded.firstOrNull { it.id == id }?.let(presenter::links)

    private fun refresh(minimumAge: Duration) {
        val since = loadedAt?.let { Duration.between(it, clock.instant()) }
        if (since != null && since < minimumAge) return
        // Only while the very first load is still in the air is the pipeline already on its
        // way with the current query. Once it has failed there is nothing running, and
        // refusing here left the failure banner offering a Retry that did nothing at all.
        if (loadedFor == null && replacing) return
        reloads.value++
    }

    private fun loadMore() {
        // Not while the listing underneath is being replaced. The generation cannot catch
        // this on its own: the replacement has already claimed the number by the time the
        // page is asked for, so both would agree and the page would be let in.
        if (replacing) return
        val query = loadedFor ?: return
        val page = nextPage ?: return
        // Taken now, so a second press before the first page lands asks for nothing. Nothing
        // else stopped it: the number only advances when a page *arrives*, so two presses
        // fetched the same page twice and appended it twice — and a list keyed by event id
        // does not survive the same id appearing on it twice.
        nextPage = null
        viewModelScope.launch {
            val joined = load(query.copy(page = page), appending = true, joining = generation)
            // Put it back if the page never came, or the button is gone for good.
            if (!joined && mineIsCurrent(generation)) nextPage = page
        }
    }

    /**
     * The day after the listing's end, appended under its own heading — or, when the
     * calendar has narrowed the listing to one day, the jump to the next one: that view
     * means "one day, only one", so it moves instead of growing.
     *
     * Refused while pages of the current day remain: skipping to tomorrow past an unshown
     * tail would silently drop the evening, and the foot that triggers this is only drawn
     * once the day is exhausted.
     */
    private fun loadNextDay() {
        val next = windowEnd?.plusDays(1) ?: return
        if (filters.value.day != null) {
            onIntent(AgendaIntent.PickDay(next))
            return
        }
        if (replacing || appendingDay || nextPage != null) return
        val query = loadedFor ?: return
        appendingDay = true
        viewModelScope.launch {
            try {
                load(query.copy(page = EventsRepository.FIRST_PAGE), appending = true, joining = generation, day = next)
            } finally {
                appendingDay = false
            }
        }
    }

    private fun mineIsCurrent(mine: Int) = mine == generation

    /**
     * Everything that belonged to the listing now gone.
     *
     * One definition, because two screens' worth of bugs came from clearing what is drawn
     * while leaving behind what it was drawn from — the favourites redraw then rebuilt the
     * old rows from `loaded` and put them back. `loadedAt` goes too: the five-second guard on
     * a manual refresh has nothing left to measure from once the listing it timed is gone.
     */
    private fun forgetListing() {
        loaded = emptyList()
        nextPage = null
        loadedFor = null
        loadedAt = null
        windowEnd = null
    }

    /**
     * [joining] is set only when appending, and names the load whose list this page belongs
     * to. Anything else starts a new one and silences everything before it.
     */
    private suspend fun load(
        query: Query,
        appending: Boolean,
        joining: Int? = null,
        day: LocalDate? = null,
    ): Boolean {
        val mine = joining ?: ++generation
        // One day for both halves of one load, so a window opened across midnight cannot ask
        // for a today and a yesterday that are not next to each other. Appending stays on the
        // day the listing ends on, which after "load tomorrow" is no longer the query's own.
        @Suppress("NAME_SHADOWING")
        val day = day
            ?: (if (appending) windowEnd else null)
            ?: query.day
            ?: today()
        if (appending) {
            return fetch(query, day, appending = true, mine = mine)
        }
        replacing = true
        try {
            replace(query, day, mine)
        } finally {
            // In a `finally` because being cancelled is the ordinary way this ends, and a flag
            // left set would refuse every later page for the life of the screen.
            if (mine == generation) replacing = false
        }
        return true
    }

    private suspend fun replace(query: Query, day: LocalDate, mine: Int) {
        // Strictly the result of *this* request, never a comparison against what was loaded
        // before. On a refresh the previous query is the same one, so "did the state move"
        // answers yes whether or not today came back — and prepending yesterday onto a list
        // that already held it produced two rows per event, duplicate keys, and a crash in
        // the list rather than the failure banner the reader should have seen.
        val arrived = fetch(query, day, appending = false, mine = mine)
        if (arrived && query.day == null) fetchYesterday(query, day, mine)
    }

    /**
     * Yesterday, prepended.
     *
     * Its failure is reported but does not clear the screen: today is on it and is the part
     * the reader came for. Reversing is what turns the newest-first page back into the order
     * the listing reads in.
     */
    private suspend fun fetchYesterday(query: Query, day: LocalDate, mine: Int) {
        val answer = events.onDate(query.asRequest(day = day.minusDays(1), newestFirst = true))
        // The request can finish in the instant between being abandoned and the next
        // suspension point, and writing state is not one — so it is asked for explicitly.
        currentCoroutineContext().ensureActive()
        if (mine != generation) return
        state.value = when (answer) {
            is ApiResult.Success -> {
                loaded = answer.value.results.reversed() + loaded
                state.value.copy(
                    days = presenter.days(loaded, marked),
                    anchorId = presenter.anchor(loaded),
                    error = null,
                )
            }
            is ApiResult.Failure -> state.value.copy(error = answer.error)
        }
    }

    /** True when the day arrived, which is what decides whether the second request is made. */
    private suspend fun fetch(query: Query, day: LocalDate, appending: Boolean, mine: Int): Boolean {
        state.value = state.value.copy(loading = true, error = null)

        val answer = events.onDate(query.asRequest(day = day, newestFirst = false))
        currentCoroutineContext().ensureActive()
        if (mine != generation) return false

        state.value = when (answer) {
            is ApiResult.Success -> {
                loadedAt = clock.instant()
                loadedFor = query.copy(page = EventsRepository.FIRST_PAGE)
                loaded = if (appending) loaded + answer.value.results else answer.value.results
                nextPage = if (answer.value.next != null) query.page + 1 else null
                windowEnd = day
                state.value.copy(
                    day = day,
                    nextDayLabel = presenter.times.dayLabel(day.plusDays(1)),
                    days = presenter.days(loaded, marked),
                    anchorId = presenter.anchor(loaded),
                    count = answer.value.count,
                    loading = false,
                    error = null,
                    showingStale = false,
                    canLoadMore = nextPage != null,
                )
            }
            /**
             * A page past the end is the end of the list, not a failure. It happens when the
             * last page was exactly full, so the client cannot tell there is nothing after it
             * without asking.
             */
            is ApiResult.Failure -> if (appending && answer.error == ApiError.Http(HTTP_NOT_FOUND)) {
                nextPage = null
                state.value.copy(loading = false, canLoadMore = false)
            } else {
                val sameQuery = loadedFor?.copy(page = EventsRepository.FIRST_PAGE) ==
                    query.copy(page = EventsRepository.FIRST_PAGE)
                // Following something re-marks the rows from `loaded` without asking the
                // server. Leaving the old query's events there while clearing the days let
                // that redraw resurrect them: the whole plain agenda reappearing under a
                // followed team's chip, with the failure banner still on it.
                if (!sameQuery) forgetListing()
                state.value.copy(
                    days = if (sameQuery) state.value.days else emptyList(),
                    nextDayLabel = if (sameQuery) state.value.nextDayLabel else null,
                    anchorId = if (sameQuery) state.value.anchorId else null,
                    loading = false,
                    error = answer.error,
                    showingStale = sameQuery && state.value.days.isNotEmpty(),
                    canLoadMore = if (sameQuery) state.value.canLoadMore else false,
                )
            }
        }
        return answer is ApiResult.Success
    }

    /** A single letter narrows nothing and costs a request across six joined tables. */
    private fun effectiveSearch(text: String) = text.trim().takeIf { it.length >= SHORTEST_SEARCH }.orEmpty()

    private data class Filters(val watchableOnly: Boolean, val narrowing: AgendaFilter?, val day: LocalDate?)

    private data class Query(
        val search: String,
        val watchableOnly: Boolean,
        val narrowing: AgendaFilter?,
        /** A single day chosen on the calendar; null is the yesterday-and-today window. */
        val day: LocalDate? = null,
        val page: Int = EventsRepository.FIRST_PAGE,
    ) {
        fun asRequest(day: LocalDate, newestFirst: Boolean) = AgendaQuery(
            date = day.toString(),
            search = search.ifBlank { null },
            watchableOnly = watchableOnly,
            team = narrowing?.id?.takeIf { narrowing.kind == FollowableKind.Teams },
            competition = narrowing?.id?.takeIf { narrowing.kind == FollowableKind.Competitions },
            newestFirst = newestFirst,
            page = page,
        )
    }

    companion object {
        const val TYPING_PAUSE_MILLIS: Long = 400
        const val SHORTEST_SEARCH: Int = 2
        val MANUAL_REFRESH_INTERVAL: Duration = Duration.ofSeconds(5)
        val STALE_AFTER: Duration = Duration.ofSeconds(60)
        private const val HTTP_NOT_FOUND = 404
    }
}

/**
 * What the agenda is showing. [day] is the day the listing is anchored on — today, whose
 * window is the day before it and it, or [chosenDay] when the calendar has narrowed it.
 */
data class AgendaUiState(
    val day: LocalDate,
    val query: String = "",
    val watchableOnly: Boolean = false,
    /** Set when the reader arrived from a followed team or competition. */
    val filter: AgendaFilter? = null,
    /** The single day chosen on the calendar; null is the yesterday-and-today window. */
    val chosenDay: LocalDate? = null,
    /**
     * What the foot of an exhausted listing offers to load, already worded ("MAÑANA · …").
     * Null until something has loaded; the foot is drawn only when [canLoadMore] is false,
     * because tomorrow must not be reachable past an unshown tail of today.
     */
    val nextDayLabel: String? = null,
    /**
     * The event the listing should open on — the first one that has not finished. Null when
     * everything in the window is over, and the listing then opens at the end.
     */
    val anchorId: Int? = null,
    val days: List<AgendaDay> = emptyList(),
    val count: Int = 0,
    val loading: Boolean = false,
    val error: ApiError? = null,
    /** The answer on screen is the previous one; the latest attempt failed. */
    val showingStale: Boolean = false,
    val canLoadMore: Boolean = false,
) {
    val isEmpty: Boolean get() = days.isEmpty() && !loading && error == null
}

sealed interface AgendaIntent {
    data class Search(val text: String) : AgendaIntent

    /** Narrow to one followed team or competition, or pass null to show everything again. */
    data class Narrow(val filter: AgendaFilter?) : AgendaIntent

    /** Show one day chosen on the calendar, or pass null to return to yesterday and today. */
    data class PickDay(val day: LocalDate?) : AgendaIntent

    data class OnlyWatchable(val only: Boolean) : AgendaIntent

    data object Refresh : AgendaIntent

    /** The screen came back to the foreground. */
    data object Resumed : AgendaIntent

    data object LoadMore : AgendaIntent

    /** Append the day after the listing's end — or move to it, when a day was chosen. */
    data object LoadNextDay : AgendaIntent

    data object DismissError : AgendaIntent
}

/**
 * The agenda narrowed to one thing the reader follows.
 *
 * It carries the name and the image as well as the id because it is drawn as a chip the moment
 * it is applied — before any response has arrived — and the strip it was pressed on already
 * holds both. Asking the server what a team is called in order to say which team is being
 * shown would be a request bought with nothing.
 */
data class AgendaFilter(
    val id: Int,
    val name: String,
    val imageUrl: String?,
    val kind: FollowableKind,
) {
    companion object {
        fun of(followable: Followable) = AgendaFilter(
            id = followable.item.id,
            name = followable.item.name,
            imageUrl = followable.item.imageUrl,
            kind = followable.kind,
        )
    }
}
