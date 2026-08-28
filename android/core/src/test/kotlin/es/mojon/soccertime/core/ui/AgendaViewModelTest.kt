package es.mojon.soccertime.core.ui

import app.cash.turbine.test
import es.mojon.soccertime.core.data.EventsRepository
import es.mojon.soccertime.core.data.Favorites
import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.model.Page
import es.mojon.soccertime.core.network.ApiError
import es.mojon.soccertime.core.network.ApiResult
import es.mojon.soccertime.core.network.Network
import es.mojon.soccertime.core.time.EventTimes
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlin.time.Duration.Companion.milliseconds
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The refresh policy, which is the only reason this class is not a plain mapper.
 *
 * Almost every assertion here is about a request that should or should not have been made. The
 * limit is thirty a minute per address, shared by both apps and by any browser on the same
 * connection, so "how many times did it ask" is the behaviour under test — which is why the
 * double records its calls rather than merely answering them.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class AgendaViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private val august30 = LocalDate.of(2026, 8, 30)

    private data class Ask(val date: String, val search: String?, val watchableOnly: Boolean, val page: Int)

    private class Recording(private val answer: Page<EventDto>) : EventsRepository {
        val asks = mutableListOf<Ask>()
        var failure: ApiError? = null
        var pageAnswer: Page<EventDto> = answer

        override suspend fun upcoming(page: Int) = onDate("", null, false, page)

        override suspend fun onDate(
            date: String,
            search: String?,
            watchableOnly: Boolean,
            page: Int,
        ): ApiResult<Page<EventDto>> {
            asks += Ask(date, search, watchableOnly, page)
            return failure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(pageAnswer)
        }
    }

    /** A clock the test moves, so staleness can be reached without waiting for it. */
    private class Movable(var now: Instant) : Clock() {
        override fun getZone(): ZoneId = ZoneId.of("UTC")
        override fun withZone(zone: ZoneId): Clock = this
        override fun instant(): Instant = now
        fun advance(by: Duration) { now = now.plus(by) }
    }

    private lateinit var repository: Recording
    private lateinit var clock: Movable

    private fun fixture(): Page<EventDto> {
        val body = checkNotNull(javaClass.classLoader?.getResourceAsStream("fixtures/events_day_page1.json"))
            .use { it.readBytes().decodeToString() }
        return Network.json.decodeFromString(body)
    }

    private val followed = MutableStateFlow(Favorites.NONE)

    private fun viewModel() = AgendaViewModel(
        events = repository,
        presenter = EventPresenter(EventTimes(clock = clock, zone = ZoneId.of("Europe/Madrid"))),
        clock = clock,
        today = august30,
        favorites = followed,
    )

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        clock = Movable(Instant.parse("2026-08-30T12:00:00Z"))
        repository = Recording(fixture())
    }

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `it loads the day it opens on, once`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        assertEquals(1, repository.asks.size)
        assertEquals("2026-08-30", repository.asks.single().date)
        assertEquals(3, model.uiState.value.days.sumOf { it.events.size })
    }

    @Test
    fun `typing a word costs one request, not one per letter`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val before = repository.asks.size

        val word = "Barcelona"
        word.indices.forEach { index ->
            model.onIntent(AgendaIntent.Search(word.take(index + 1)))
            advanceTimeBy(50.milliseconds)
        }
        advanceUntilIdle()

        assertEquals(1, repository.asks.size - before)
        assertEquals(word, repository.asks.last().search)
    }

    @Test
    fun `a single letter is not a search and costs nothing`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val before = repository.asks.size

        model.onIntent(AgendaIntent.Search("B"))
        advanceUntilIdle()

        assertEquals(0, repository.asks.size - before)
        assertEquals("B", model.uiState.value.query)
    }

    @Test
    fun `clearing the box asks for the unfiltered day again`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.Search("Barcelona"))
        advanceUntilIdle()
        val before = repository.asks.size

        model.onIntent(AgendaIntent.Search(""))
        advanceUntilIdle()

        assertEquals(1, repository.asks.size - before)
        assertNull(repository.asks.last().search)
    }

    @Test
    fun `narrowing to what can be opened is a filter the server applies`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        model.onIntent(AgendaIntent.OnlyWatchable(true))
        advanceUntilIdle()

        assertTrue(repository.asks.last().watchableOnly)
        assertTrue(model.uiState.value.watchableOnly)
    }

    @Test
    fun `a refresh within five seconds of the last one does nothing`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = repository.asks.size

        clock.advance(Duration.ofSeconds(4))
        repeat(5) { model.onIntent(AgendaIntent.Refresh) }
        advanceUntilIdle()

        assertEquals("four seconds on, the answer cannot have changed", loaded, repository.asks.size)
    }

    @Test
    fun `a refresh after five seconds does ask`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = repository.asks.size

        clock.advance(Duration.ofSeconds(6))
        model.onIntent(AgendaIntent.Refresh)
        advanceUntilIdle()

        assertEquals(loaded + 1, repository.asks.size)
    }

    @Test
    fun `coming back to a fresh screen does not reload it`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = repository.asks.size

        clock.advance(Duration.ofSeconds(30))
        model.onIntent(AgendaIntent.Resumed)
        advanceUntilIdle()

        assertEquals(loaded, repository.asks.size)
    }

    @Test
    fun `coming back to one over a minute old reloads it`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = repository.asks.size

        clock.advance(Duration.ofSeconds(61))
        model.onIntent(AgendaIntent.Resumed)
        advanceUntilIdle()

        assertEquals(loaded + 1, repository.asks.size)
    }

    @Test
    fun `a failure keeps the last good answer on screen and says so`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = model.uiState.value.days

        repository.failure = ApiError.Offline
        clock.advance(Duration.ofSeconds(61))
        model.onIntent(AgendaIntent.Resumed)
        advanceUntilIdle()

        model.uiState.test {
            val state = awaitItem()
            assertEquals("the rows are still there", loaded, state.days)
            assertEquals(ApiError.Offline, state.error)
            assertTrue(state.showingStale)
            assertFalse(state.loading)
        }
    }

    @Test
    fun `a failure on a query that moved shows nothing rather than the wrong day`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        repository.failure = ApiError.RateLimited(retryAfterSeconds = 12)
        model.onIntent(AgendaIntent.PickDate(august30.plusDays(1)))
        advanceUntilIdle()

        val state = model.uiState.value
        assertEquals(emptyList<AgendaDay>(), state.days)
        assertEquals(ApiError.RateLimited(12), state.error)
        assertFalse("stale would be a lie: this is a different day", state.showingStale)
    }

    @Test
    fun `following a team re-marks the rows without asking the server again`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = repository.asks.size
        val everyRow = model.uiState.value.days.flatMap { it.events }
        assertTrue("nothing is marked yet", everyRow.none { it.favorite })

        val aTeamOnScreen = checkNotNull(repository.pageAnswer.results.first { it.local != null }.local).id
        followed.value = Favorites(teamIds = setOf(aTeamOnScreen))
        advanceUntilIdle()

        assertEquals("marking is a redraw, not a request", loaded, repository.asks.size)
        assertTrue(model.uiState.value.days.flatMap { it.events }.any { it.favorite })
    }

    @Test
    fun `a page past the end is the end of the list, not an error`() = runTest(dispatcher) {
        repository.pageAnswer = repository.pageAnswer.copy(next = "https://www.mojon.es/…?page=2")
        val model = viewModel()
        advanceUntilIdle()
        assertTrue(model.uiState.value.canLoadMore)

        repository.failure = ApiError.Http(404)
        model.onIntent(AgendaIntent.LoadMore)
        advanceUntilIdle()

        val state = model.uiState.value
        assertNull("a 404 while appending is not shown to anybody", state.error)
        assertFalse(state.canLoadMore)
    }
}
