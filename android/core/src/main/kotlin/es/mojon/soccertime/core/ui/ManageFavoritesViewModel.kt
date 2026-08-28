package es.mojon.soccertime.core.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import es.mojon.soccertime.core.data.CatalogRepository
import es.mojon.soccertime.core.data.FavoritesStore
import es.mojon.soccertime.core.data.FollowedItem
import es.mojon.soccertime.core.data.Following
import es.mojon.soccertime.core.network.ApiError
import es.mojon.soccertime.core.network.ApiResult
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/**
 * Choosing what to follow.
 *
 * Searching is debounced and a query under two characters is treated as none, for the same
 * reason as on the agenda: a single letter narrows 4,796 teams to something nobody wanted and
 * costs a request to do it.
 *
 * Following something writes to the store and nothing else. The list on screen re-marks
 * itself from the store's own flow, which means the tick appearing is proof the choice was
 * written rather than a hopeful redraw that a failed write would leave lying.
 */
@OptIn(ExperimentalCoroutinesApi::class, FlowPreview::class)
class ManageFavoritesViewModel(
    private val catalog: CatalogRepository,
    private val store: FavoritesStore,
) : ViewModel() {

    private val search = MutableStateFlow("")
    private val kind = MutableStateFlow(FollowableKind.Teams)
    private val state = MutableStateFlow(ManageUiState())

    val uiState: StateFlow<ManageUiState> = state.asStateFlow()

    private var found: List<FollowedItem> = emptyList()

    /**
     * Which list the rows on screen came from.
     *
     * Not the same as the tab. Switching tabs changes the tab at once and then waits on the
     * network without clearing the rows, so for those seconds — or for good, if that load
     * fails — the screen shows teams under a heading that says competitions. Anything that
     * reads the tab to decide what a row *is* gets it wrong for that whole window.
     */
    private var foundKind: FollowableKind = FollowableKind.Teams

    /** Bumped to ask the same question again, which a `StateFlow` alone will not do. */
    private val reloads = MutableStateFlow(0)

    init {
        viewModelScope.launch {
            combine(
                search.debounce { if (it.isEmpty()) 0L else AgendaViewModel.TYPING_PAUSE_MILLIS }
                    .map { it.trim().takeIf { text -> text.length >= AgendaViewModel.SHORTEST_SEARCH }.orEmpty() }
                    .distinctUntilChanged(),
                kind,
                reloads,
            ) { text, which, _ -> text to which }
                .collectLatest { (text, which) -> load(text, which) }
        }

        viewModelScope.launch {
            store.following.collect { current ->
                state.value = state.value.copy(following = current, results = mark(found, current))
            }
        }
    }

    fun onIntent(intent: ManageIntent) {
        when (intent) {
            is ManageIntent.Search -> {
                search.value = intent.text
                state.value = state.value.copy(query = intent.text)
            }
            is ManageIntent.Show -> {
                kind.value = intent.kind
                state.value = state.value.copy(kind = intent.kind)
            }
            // The row says what it is. Reading the tab instead wrote a team into the
            // competitions of the store — persistently, and `Favorites.covers` then matched
            // its id against every event's competition.
            is ManageIntent.Follow -> viewModelScope.launch {
                when (intent.kind) {
                    FollowableKind.Teams -> store.setTeam(intent.item, intent.followed)
                    FollowableKind.Competitions -> store.setCompetition(intent.item, intent.followed)
                }
            }
            ManageIntent.Retry -> reloads.value++
            ManageIntent.DismissError -> state.value = state.value.copy(error = null)
        }
    }

    private suspend fun load(search: String, which: FollowableKind) {
        state.value = state.value.copy(loading = true, error = null)

        val answer = when (which) {
            FollowableKind.Teams -> catalog.teams(search.ifBlank { null })
                .map { page -> page.results.map { FollowedItem(it.id, it.name, it.crest?.url) } to page.count }
            FollowableKind.Competitions -> catalog.competitions(search.ifBlank { null })
                .map { page ->
                    page.results.map { FollowedItem(it.id, it.name, it.flag?.image?.url) } to page.count
                }
        }

        // Typing again abandons this search; the answer to the one before it must not land
        // on the list, and a request can return in the instant before the next suspension.
        currentCoroutineContext().ensureActive()

        state.value = when (answer) {
            is ApiResult.Success -> {
                found = answer.value.first
                foundKind = which
                state.value.copy(
                    results = mark(found, state.value.following),
                    total = answer.value.second,
                    loading = false,
                    error = null,
                )
            }
            is ApiResult.Failure -> state.value.copy(loading = false, error = answer.error)
        }
    }

    private fun mark(items: List<FollowedItem>, following: Following): List<FollowableUi> {
        val followed = when (foundKind) {
            FollowableKind.Teams -> following.selection.teamIds
            FollowableKind.Competitions -> following.selection.competitionIds
        }
        return items.map {
            FollowableUi(item = it, followed = it.id in followed, kind = foundKind)
        }
    }

    private inline fun <T, R> ApiResult<T>.map(transform: (T) -> R): ApiResult<R> = when (this) {
        is ApiResult.Success -> ApiResult.Success(transform(value))
        is ApiResult.Failure -> this
    }
}

enum class FollowableKind { Teams, Competitions }

/** [kind] is the list this row came from, which is not always the tab now on screen. */
data class FollowableUi(
    val item: FollowedItem,
    val followed: Boolean,
    val kind: FollowableKind,
)

data class ManageUiState(
    val kind: FollowableKind = FollowableKind.Teams,
    val query: String = "",
    val results: List<FollowableUi> = emptyList(),
    val following: Following = Following(),
    val total: Int = 0,
    val loading: Boolean = false,
    val error: ApiError? = null,
) {
    val nothingFound: Boolean get() = results.isEmpty() && !loading && error == null
}

sealed interface ManageIntent {
    data class Search(val text: String) : ManageIntent

    data class Show(val kind: FollowableKind) : ManageIntent

    data class Follow(
        val item: FollowedItem,
        val followed: Boolean,
        val kind: FollowableKind,
    ) : ManageIntent

    /** Ask the same question again. Re-sending the search would be deduplicated away. */
    data object Retry : ManageIntent

    data object DismissError : ManageIntent
}
