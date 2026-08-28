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
 * hour would have nothing to show. Moving between days, and a calendar, are deliberately not
 * here yet.
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
    /**
     * Taken from the presenter, which is the only thing here that knows where the reader is.
     * Asking `LocalDate.now(clock)` was asking UTC: in Spain, between midnight and two in the
     * morning, that is yesterday — so the window fetched was the day before the one every
     * heading on it named, in exactly the hours this two-day window exists to serve.
     */
    private val today: LocalDate = presenter.times.today(),
    favorites: Flow<Favorites> = flowOf(Favorites.NONE),
) : ViewModel() {

    private val search = MutableStateFlow("")
    private val filters = MutableStateFlow(Filters(watchableOnly = false, narrowing = null))
    private val state = MutableStateFlow(AgendaUiState(day = today))

    val uiState: StateFlow<AgendaUiState> = state.asStateFlow()

    private var loadedAt: Instant? = null
    private var loaded: List<EventDto> = emptyList()
    private var loadedFor: Query? = null
    private var nextPage: Int? = null
    private var marked: Favorites = Favorites.NONE

    init {
        viewModelScope.launch {
            combine(
                search.debounce { if (it.isEmpty()) 0L else TYPING_PAUSE_MILLIS }
                    .map(::effectiveSearch)
                    .distinctUntilChanged(),
                filters,
            ) { text, applied -> Query(text, applied.watchableOnly, applied.narrowing) }
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
                filters.value = filters.value.copy(narrowing = intent.filter)
                state.value = state.value.copy(filter = intent.filter)
            }
            is AgendaIntent.OnlyWatchable -> {
                filters.value = filters.value.copy(watchableOnly = intent.only)
                state.value = state.value.copy(watchableOnly = intent.only)
            }
            AgendaIntent.Refresh -> refresh(minimumAge = MANUAL_REFRESH_INTERVAL)
            AgendaIntent.Resumed -> refresh(minimumAge = STALE_AFTER)
            AgendaIntent.LoadMore -> loadMore()
            AgendaIntent.DismissError -> state.value = state.value.copy(error = null)
        }
    }

    /** The two sides and the competition of one row, for the panel that follows them. */
    fun followablesFor(id: Int): List<Followable> =
        loaded.firstOrNull { it.id == id }?.let(presenter::followables).orEmpty()

    /** The links of one row, built from the response the row was drawn from. */
    fun linksFor(id: Int): EventLinks? = loaded.firstOrNull { it.id == id }?.let(presenter::links)

    private fun refresh(minimumAge: Duration) {
        val since = loadedAt?.let { Duration.between(it, clock.instant()) }
        if (since != null && since < minimumAge) return
        val query = loadedFor ?: return
        viewModelScope.launch { load(query, appending = false) }
    }

    private fun loadMore() {
        val query = loadedFor ?: return
        val page = nextPage ?: return
        viewModelScope.launch { load(query.copy(page = page), appending = true) }
    }

    private suspend fun load(query: Query, appending: Boolean) {
        if (appending) {
            fetch(query, appending = true)
            return
        }
        // Strictly the result of *this* request, never a comparison against what was loaded
        // before. On a refresh the previous query is the same one, so "did the state move"
        // answers yes whether or not today came back — and prepending yesterday onto a list
        // that already held it produced two rows per event, duplicate keys, and a crash in
        // the list rather than the failure banner the reader should have seen.
        if (fetch(query, appending = false)) fetchYesterday(query)
    }

    /**
     * Yesterday, prepended.
     *
     * Its failure is reported but does not clear the screen: today is on it and is the part
     * the reader came for. Reversing is what turns the newest-first page back into the order
     * the listing reads in.
     */
    private suspend fun fetchYesterday(query: Query) {
        val answer = events.onDate(query.asRequest(day = today.minusDays(1), newestFirst = true))
        // The request can finish in the instant between being abandoned and the next
        // suspension point, and writing state is not one — so it is asked for explicitly.
        currentCoroutineContext().ensureActive()
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
    private suspend fun fetch(query: Query, appending: Boolean): Boolean {
        state.value = state.value.copy(loading = true, error = null)

        val answer = events.onDate(query.asRequest(day = today, newestFirst = false))
        currentCoroutineContext().ensureActive()

        state.value = when (answer) {
            is ApiResult.Success -> {
                loadedAt = clock.instant()
                loadedFor = query.copy(page = EventsRepository.FIRST_PAGE)
                loaded = if (appending) loaded + answer.value.results else answer.value.results
                nextPage = if (answer.value.next != null) query.page + 1 else null
                state.value.copy(
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
                state.value.copy(
                    days = if (sameQuery) state.value.days else emptyList(),
                    loading = false,
                    error = answer.error,
                    showingStale = sameQuery && state.value.days.isNotEmpty(),
                )
            }
        }
        return answer is ApiResult.Success
    }

    /** A single letter narrows nothing and costs a request across six joined tables. */
    private fun effectiveSearch(text: String) = text.trim().takeIf { it.length >= SHORTEST_SEARCH }.orEmpty()

    private data class Filters(val watchableOnly: Boolean, val narrowing: AgendaFilter?)

    private data class Query(
        val search: String,
        val watchableOnly: Boolean,
        val narrowing: AgendaFilter?,
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
 * What the agenda is showing. [day] is today; the window is the day before it and it.
 */
data class AgendaUiState(
    val day: LocalDate,
    val query: String = "",
    val watchableOnly: Boolean = false,
    /** Set when the reader arrived from a followed team or competition. */
    val filter: AgendaFilter? = null,
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

    data class OnlyWatchable(val only: Boolean) : AgendaIntent

    data object Refresh : AgendaIntent

    /** The screen came back to the foreground. */
    data object Resumed : AgendaIntent

    data object LoadMore : AgendaIntent

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
