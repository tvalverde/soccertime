package es.mojon.soccertime.core.ui

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import es.mojon.soccertime.core.data.CatalogRepository
import es.mojon.soccertime.core.data.FavoritesStore
import es.mojon.soccertime.core.data.FollowedItem
import es.mojon.soccertime.core.model.CompetitionDto
import es.mojon.soccertime.core.model.Page
import es.mojon.soccertime.core.model.TeamDto
import es.mojon.soccertime.core.network.ApiError
import es.mojon.soccertime.core.network.ApiResult
import es.mojon.soccertime.core.network.Network
import kotlin.time.Duration.Companion.milliseconds
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * Choosing what to follow, against the real search results the API returns for "Athletic" —
 * including the two rows whose crest is missing, which is a state the API says is normal.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ManageFavoritesViewModelTest {

    @get:Rule
    val folder = TemporaryFolder()

    private val dispatcher = StandardTestDispatcher()

    private class Recording(
        private val teams: Page<TeamDto>,
        private val competitions: Page<CompetitionDto>,
    ) : CatalogRepository {
        val teamSearches = mutableListOf<String?>()
        val competitionSearches = mutableListOf<String?>()
        var failure: ApiError? = null

        override suspend fun teams(search: String?, page: Int): ApiResult<Page<TeamDto>> {
            teamSearches += search
            return failure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(teams)
        }

        override suspend fun competitions(search: String?, page: Int): ApiResult<Page<CompetitionDto>> {
            competitionSearches += search
            return failure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(competitions)
        }
    }

    private lateinit var catalog: Recording
    private lateinit var store: FavoritesStore
    private lateinit var storeScope: CoroutineScope

    private inline fun <reified T> fixture(name: String): Page<T> {
        val body = checkNotNull(javaClass.classLoader?.getResourceAsStream("fixtures/$name"))
            .use { it.readBytes().decodeToString() }
        return Network.json.decodeFromString(body)
    }

    private fun viewModel() = ManageFavoritesViewModel(catalog, store)

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        storeScope = CoroutineScope(UnconfinedTestDispatcher() + Job())
        store = FavoritesStore(
            PreferenceDataStoreFactory.create(scope = storeScope) {
                folder.root.resolve("favorites.preferences_pb")
            },
        )
        catalog = Recording(
            teams = fixture("teams_search.json"),
            competitions = fixture("competitions_search.json"),
        )
    }

    @After
    fun tearDown() {
        storeScope.cancel()
        Dispatchers.resetMain()
    }

    @Test
    fun `it opens on the directory, unfiltered`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        assertEquals(listOf(null), catalog.teamSearches)
        assertTrue(model.uiState.value.results.isNotEmpty())
        assertTrue(model.uiState.value.results.none { it.followed })
    }

    @Test
    fun `typing a name costs one request, not one per letter`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val before = catalog.teamSearches.size

        val word = "Athletic"
        word.indices.forEach { index ->
            model.onIntent(ManageIntent.Search(word.take(index + 1)))
            advanceTimeBy(50.milliseconds)
        }
        advanceUntilIdle()

        assertEquals(1, catalog.teamSearches.size - before)
        assertEquals(word, catalog.teamSearches.last())
    }

    @Test
    fun `a single letter is not a search`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val before = catalog.teamSearches.size

        model.onIntent(ManageIntent.Search("A"))
        advanceUntilIdle()

        assertEquals(0, catalog.teamSearches.size - before)
    }

    @Test
    fun `switching to competitions asks the other directory`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        model.onIntent(ManageIntent.Show(FollowableKind.Competitions))
        advanceUntilIdle()

        assertEquals(1, catalog.competitionSearches.size)
        assertEquals(FollowableKind.Competitions, model.uiState.value.kind)
        assertTrue(model.uiState.value.results.isNotEmpty())
    }

    @Test
    fun `following a team is written and the row shows it`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val first = model.uiState.value.results.first().item
        val before = catalog.teamSearches.size

        model.onIntent(ManageIntent.Follow(first, followed = true))
        advanceUntilIdle()

        assertEquals("the store is what marks it, not a hopeful redraw", listOf(first), store.following.first().teams)
        assertTrue(model.uiState.value.results.first { it.item.id == first.id }.followed)
        assertEquals("marking costs no request", before, catalog.teamSearches.size)
    }

    @Test
    fun `unfollowing removes it again`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val first = model.uiState.value.results.first().item
        model.onIntent(ManageIntent.Follow(first, followed = true))
        advanceUntilIdle()

        model.onIntent(ManageIntent.Follow(first, followed = false))
        advanceUntilIdle()

        assertTrue(store.following.first().teams.isEmpty())
        assertFalse(model.uiState.value.results.first { it.item.id == first.id }.followed)
    }

    @Test
    fun `a team on the competitions tab is followed as a competition`() = runTest(dispatcher) {
        val model = viewModel()
        model.onIntent(ManageIntent.Show(FollowableKind.Competitions))
        advanceUntilIdle()
        val first = model.uiState.value.results.first().item

        model.onIntent(ManageIntent.Follow(first, followed = true))
        advanceUntilIdle()

        val following = store.following.first()
        assertEquals(listOf(first), following.competitions)
        assertTrue("it must not land among the teams", following.teams.isEmpty())
    }

    @Test
    fun `a row whose crest the api never sent is still a row`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        val shown = model.uiState.value.results
        assertTrue(shown.isNotEmpty())
        assertTrue("every result is named", shown.all { it.item.name.isNotBlank() })
    }

    @Test
    fun `a failure is reported and leaves nothing half-drawn`() = runTest(dispatcher) {
        catalog.failure = ApiError.RateLimited(retryAfterSeconds = 9)
        val model = viewModel()
        advanceUntilIdle()

        val state = model.uiState.value
        assertEquals(ApiError.RateLimited(9), state.error)
        assertTrue(state.results.isEmpty())
        assertFalse(state.loading)
    }
}
