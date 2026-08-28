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
 * would spend a fifth of a minute's budget on one screen. One request for the window and a
 * local filter costs one.
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

    init {
        viewModelScope.launch {
            favorites.collect { chosen ->
                val wasEmpty = following.isEmpty
                following = chosen
                state.value = state.value.copy(following = chosen, chosenNothing = chosen.isEmpty)

                when {
                    chosen.isEmpty -> {
                        loaded = emptyList()
                        state.value = state.value.copy(days = emptyList(), error = null)
                    }
                    // Nothing was fetched while the selection was empty, so the first choice
                    // is what triggers the only load this screen makes.
                    wasEmpty || loaded.isEmpty() -> load()
                    // Otherwise the window on screen already contains the answer: following
                    // one more team narrows the same list rather than asking for another.
                    else -> state.value = state.value.copy(days = present())
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
        if (following.isEmpty) return
        val since = loadedAt?.let { Duration.between(it, clock.instant()) }
        if (since != null && since < minimumAge) return
        viewModelScope.launch { load() }
    }

    private suspend fun load() {
        state.value = state.value.copy(loading = true, error = null)

        state.value = when (val answer = events.upcoming()) {
            is ApiResult.Success -> {
                loadedAt = clock.instant()
                loaded = answer.value.results
                state.value.copy(days = present(), loading = false, error = null, showingStale = false)
            }
            is ApiResult.Failure -> state.value.copy(
                loading = false,
                error = answer.error,
                showingStale = state.value.days.isNotEmpty(),
            )
        }
    }

    /**
     * Nothing is marked here. Every row on this screen is a favourite already, and a mark
     * every row carries marks nothing — the same rule the site's own agenda item follows.
     */
    private fun present(): List<AgendaDay> {
        val now = clock.instant()
        val opens = now.minus(HOURS_BEFORE)
        val closes = now.plus(DAYS_AHEAD)
        val inWindow = loaded.filter { event ->
            val at = presenter.times.instantAt(event.date) ?: return@filter false
            !at.isBefore(opens) && !at.isAfter(closes)
        }
        return presenter.days(following.filter(inWindow), following, markFavorites = false)
    }

    companion object {
        /** Both mirror `in_window`'s defaults on the site's favourites view. */
        val HOURS_BEFORE: Duration = Duration.ofHours(3)
        val DAYS_AHEAD: Duration = Duration.ofDays(3)

        val MANUAL_REFRESH_INTERVAL: Duration = AgendaViewModel.MANUAL_REFRESH_INTERVAL
        val STALE_AFTER: Duration = AgendaViewModel.STALE_AFTER
    }
}

data class FavoritesUiState(
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
