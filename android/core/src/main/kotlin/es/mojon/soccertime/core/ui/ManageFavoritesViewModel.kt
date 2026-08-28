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

    init {
        viewModelScope.launch {
            combine(
                search.debounce { if (it.isEmpty()) 0L else AgendaViewModel.TYPING_PAUSE_MILLIS }
                    .map { it.trim().takeIf { text -> text.length >= AgendaViewModel.SHORTEST_SEARCH }.orEmpty() }
                    .distinctUntilChanged(),
                kind,
            ) { text, which -> text to which }
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
            is ManageIntent.Follow -> viewModelScope.launch {
                when (state.value.kind) {
                    FollowableKind.Teams -> store.setTeam(intent.item, intent.followed)
                    FollowableKind.Competitions -> store.setCompetition(intent.item, intent.followed)
                }
            }
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

        state.value = when (answer) {
            is ApiResult.Success -> {
                found = answer.value.first
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
        val followed = when (state.value.kind) {
            FollowableKind.Teams -> following.selection.teamIds
            FollowableKind.Competitions -> following.selection.competitionIds
        }
        return items.map { FollowableUi(item = it, followed = it.id in followed) }
    }

    private inline fun <T, R> ApiResult<T>.map(transform: (T) -> R): ApiResult<R> = when (this) {
        is ApiResult.Success -> ApiResult.Success(transform(value))
        is ApiResult.Failure -> this
    }
}

enum class FollowableKind { Teams, Competitions }

data class FollowableUi(val item: FollowedItem, val followed: Boolean)

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

    data class Follow(val item: FollowedItem, val followed: Boolean) : ManageIntent

    data object DismissError : ManageIntent
}
