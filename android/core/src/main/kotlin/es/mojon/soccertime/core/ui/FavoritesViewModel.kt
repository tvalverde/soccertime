package es.mojon.soccertime.core.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import es.mojon.soccertime.core.data.EventsRepository
import es.mojon.soccertime.core.data.Favorites
import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.network.ApiError
import es.mojon.soccertime.core.network.ApiResult
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * The landing screen: what the reader follows, and when.
 *
 * Two decisions carry this class.
 *
 * The first is that the filtering happens here rather than through the API. There is no
 * per-caller state on the server, so the alternative is one request per followed team — and on
 * a limit of thirty a minute shared by every device on the connection, following six teams
 * would spend a fifth of a minute's budget on one screen. Fetching the window and filtering
 * locally costs the same handful of pages whether one team is followed or six.
 *
 * The window is fetched **whole**, page by page, because one page of it is a different and
 * wrong answer: a Saturday holds well over a hundred events, so the first hundred of
 * "today onwards" once ended at teatime the same day — and everything the reader followed
 * tomorrow was quietly missing while the site showed it. The site filters server-side and
 * never had the problem.
 *
 * The second is that following nothing asks for nothing. A reader who has chosen nothing gets
 * the screen that invites them to choose, and there is no answer that screen needs — so no
 * request is made at all, which also means a fresh install works before it has ever been
 * online.
 *
 * The window mirrors `Event.objects.in_window(hours_before=3, days_ahead=3)`, which is what
 * the site's own favourites page uses: three hours back so something that started while you
 * were on your way home is still there, three days forward so the page stays a handful.
 */
class FavoritesViewModel(
    private val events: EventsRepository,
    private val presenter: EventPresenter,
    favorites: Flow<Favorites>,
    private val clock: Clock = Clock.systemUTC(),
) : ViewModel() {

    private val state = MutableStateFlow(FavoritesUiState())
    val uiState: StateFlow<FavoritesUiState> = state.asStateFlow()

    private var loadedAt: Instant? = null
    private var loaded: List<EventDto> = emptyList()
    private var following: Favorites = Favorites.NONE

    /**
     * Whether a load is already in the air.
     *
     * Nothing here cancels anything — this screen makes one load and has no query to
     * change — so two overlapping loads would simply both answer, and the older could answer
     * last and put a staler window on screen than the one it replaced. It only takes a load
     * outliving the minute that makes the next resume ask again.
     */
    private var inFlight = false

    init {
        viewModelScope.launch {
            favorites.collect { chosen ->
                val wasEmpty = following.isEmpty
                following = chosen
                state.value = state.value.copy(following = chosen, chosenNothing = chosen.isEmpty)

                when {
                    chosen.isEmpty -> {
                        loaded = emptyList()
                        state.value = state.value.copy(days = emptyList(), anchorId = null, error = null)
                    }
                    // Nothing was fetched while the selection was empty, so the first choice
                    // is what triggers the only load this screen makes.
                    wasEmpty || loaded.isEmpty() -> load()
                    // Otherwise the window on screen already contains the answer: following
                    // one more team narrows the same list rather than asking for another.
                    else -> state.value = show(state.value)
                }
            }
        }
    }

    fun onIntent(intent: FavoritesIntent) {
        when (intent) {
            FavoritesIntent.Refresh -> refresh(MANUAL_REFRESH_INTERVAL)
            FavoritesIntent.Resumed -> refresh(STALE_AFTER)
            FavoritesIntent.DismissError -> state.value = state.value.copy(error = null)
        }
    }

    /** The two sides and the competition of one row, for the panel that follows them. */
    fun followablesFor(id: Int): List<Followable> =
        loaded.firstOrNull { it.id == id }?.let(presenter::followables).orEmpty()

    /** The links of one row, built from the response the row was drawn from. */
    fun linksFor(id: Int): EventLinks? = loaded.firstOrNull { it.id == id }?.let(presenter::links)

    private fun refresh(minimumAge: Duration) {
        if (following.isEmpty || inFlight) return
        val since = loadedAt?.let { Duration.between(it, clock.instant()) }
        if (since != null && since < minimumAge) return
        viewModelScope.launch { load() }
    }

    private suspend fun load() {
        inFlight = true
        try {
            fetch()
        } finally {
            inFlight = false
        }
    }

    private suspend fun fetch() {
        state.value = state.value.copy(loading = true, error = null)

        // The API reads its day filters in Europe/Madrid and this clock names no zone, so
        // each bound is widened by a day and `shown()` applies the exact window locally.
        val now = clock.instant()
        val from = LocalDate.ofInstant(now.minus(HOURS_BEFORE), ZoneOffset.UTC).minusDays(1)
        val until = LocalDate.ofInstant(now.plus(DAYS_AHEAD), ZoneOffset.UTC).plusDays(1)

        val window = mutableListOf<EventDto>()
        var page = EventsRepository.FIRST_PAGE
        while (true) {
            val answer = events.upcoming(from, until, page)
            // The request can return in the instant between this coroutine being abandoned
            // and its next suspension point, and writing state is not one.
            currentCoroutineContext().ensureActive()

            when (answer) {
                is ApiResult.Success -> {
                    window += answer.value.results
                    if (answer.value.next != null && page < LAST_WINDOW_PAGE) {
                        page++
                        continue
                    }
                    loadedAt = clock.instant()
                    loaded = window
                    state.value = show(state.value).copy(loading = false, error = null, showingStale = false)
                    return
                }
                // A page that never came leaves a window with a silent gap at its end —
                // exactly the wrong answer this walk exists to avoid — so the whole load
                // fails and whatever was on screen stays, marked stale.
                is ApiResult.Failure -> {
                    state.value = state.value.copy(
                        loading = false,
                        error = answer.error,
                        showingStale = state.value.days.isNotEmpty(),
                    )
                    return
                }
            }
        }
    }

    /**
     * Nothing is marked here. Every row on this screen is a favourite already, and a mark
     * every row carries marks nothing — the same rule the site's own agenda item follows.
     */
    /** The events this screen actually draws: inside the window, and covered by the selection. */
    private fun shown(): List<EventDto> {
        val now = clock.instant()
        val opens = now.minus(HOURS_BEFORE)
        val closes = now.plus(DAYS_AHEAD)
        val inWindow = loaded.filter { event ->
            val at = presenter.times.instantAt(event.date) ?: return@filter false
            !at.isBefore(opens) && !at.isAfter(closes)
        }
        return following.filter(inWindow)
    }

    /**
     * The rows and where to open on them, from one reading of what is shown.
     *
     * The anchor has to come from the drawn events rather than from everything fetched, or it
     * could name a row the window or the selection has filtered out — and a listing told to
     * open on something that is not on it opens nowhere.
     */
    private fun show(current: FavoritesUiState): FavoritesUiState {
        val events = shown()
        return current.copy(
            days = presenter.days(events, following, markFavorites = false),
            anchorId = presenter.anchor(events),
        )
    }

    companion object {
        /** Both mirror `in_window`'s defaults on the site's favourites view. */
        val HOURS_BEFORE: Duration = Duration.ofHours(3)
        val DAYS_AHEAD: Duration = Duration.ofDays(3)

        /**
         * Where the walk stops even if the server still offers more. Ten pages is a
         * thousand events — three times the busiest window measured — and already a third
         * of the thirty-a-minute budget every device on the connection shares, which is
         * the resource this cap protects.
         */
        const val LAST_WINDOW_PAGE: Int = 10

        val MANUAL_REFRESH_INTERVAL: Duration = AgendaViewModel.MANUAL_REFRESH_INTERVAL
        val STALE_AFTER: Duration = AgendaViewModel.STALE_AFTER
    }
}

data class FavoritesUiState(
    /** The row to open on: the one nearest to now, as on the agenda. */
    val anchorId: Int? = null,
    val following: Favorites = Favorites.NONE,
    val days: List<AgendaDay> = emptyList(),
    val loading: Boolean = false,
    val error: ApiError? = null,
    val showingStale: Boolean = false,
    /** Nothing has been followed yet: the screen invites a choice rather than showing a void. */
    val chosenNothing: Boolean = true,
) {
    /** Following something, and none of it is on in the next three days. */
    val nothingComingUp: Boolean
        get() = !chosenNothing && days.isEmpty() && !loading && error == null
}

sealed interface FavoritesIntent {
    data object Refresh : FavoritesIntent

    data object Resumed : FavoritesIntent

    data object DismissError : FavoritesIntent
}
