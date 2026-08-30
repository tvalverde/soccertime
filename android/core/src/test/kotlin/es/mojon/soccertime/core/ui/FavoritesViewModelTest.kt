package es.mojon.soccertime.core.ui

import es.mojon.soccertime.core.data.AgendaQuery
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
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The landing screen, whose two interesting behaviours are both about not asking: following
 * nothing makes no request at all, and following one more team narrows what is already here.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class FavoritesViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    private class Recording(var answer: Page<EventDto>) : EventsRepository {
        var calls = 0
        var failure: ApiError? = null

        /** Pages past the first, by number. `next` is derived from whether one follows. */
        val later = mutableMapOf<Int, Page<EventDto>>()
        var failOnPage: Int? = null
        var askedFrom: LocalDate? = null
        var askedUntil: LocalDate? = null

        override suspend fun upcoming(from: LocalDate, until: LocalDate, page: Int): ApiResult<Page<EventDto>> {
            calls++
            askedFrom = from
            askedUntil = until
            failure?.let { return ApiResult.Failure(it) }
            failOnPage?.takeIf { it == page }?.let { return ApiResult.Failure(ApiError.Offline) }
            val body = if (page == EventsRepository.FIRST_PAGE) answer else later.getValue(page)
            return ApiResult.Success(body.copy(next = "page=${page + 1}".takeIf { later.containsKey(page + 1) }))
        }

        override suspend fun onDate(query: AgendaQuery) =
            upcoming(LocalDate.EPOCH, LocalDate.EPOCH, query.page)

        override suspend fun days(from: LocalDate, until: LocalDate, team: Int?, competition: Int?) =
            ApiResult.Success(emptyList<LocalDate>())
    }

    private class Movable(var now: Instant) : Clock() {
        override fun getZone(): ZoneId = ZoneId.of("UTC")
        override fun withZone(zone: ZoneId): Clock = this
        override fun instant(): Instant = now
        fun advance(by: Duration) { now = now.plus(by) }
    }

    /** The recorded day, re-dated around a fixed "now" so the window can be exercised. */
    private lateinit var repository: Recording
    private lateinit var clock: Movable
    private lateinit var followed: MutableStateFlow<Favorites>

    /**
     * An hour before the earliest event in the recorded page, which starts at 22:00 UTC. The
     * window is three hours back and three days forward, so this puts the whole fixture just
     * ahead of the reader — where a landing screen is supposed to find things.
     */
    private val now = Instant.parse("2026-08-29T21:00:00Z")

    private fun page(): Page<EventDto> {
        val body = checkNotNull(javaClass.classLoader?.getResourceAsStream("fixtures/events_day_page1.json"))
            .use { it.readBytes().decodeToString() }
        return Network.json.decodeFromString(body)
    }

    private fun viewModel() = FavoritesViewModel(
        events = repository,
        presenter = EventPresenter(EventTimes(clock = clock, zone = ZoneId.of("Europe/Madrid"))),
        favorites = followed,
        clock = clock,
    )

    private val aFollowedTeam: Int
        get() = checkNotNull(repository.answer.results.first { it.local != null }.local).id

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        clock = Movable(now)
        repository = Recording(page())
        followed = MutableStateFlow(Favorites.NONE)
    }

    @After
    fun tearDown() = Dispatchers.resetMain()

    /**
     * The screen has to say where to open, like the agenda does. It said nothing, so the
     * television opened it at the top by default and the phone — which passed no anchor at
     * all — fell through to the "open at the end" branch and scrolled to its last row.
     */
    @Test
    fun `the screen says which row to open on`() = runTest(dispatcher) {
        // Every competition on the recorded page, so more than one row is covered and "the
        // first" and "the last" are different answers.
        followed.value = Favorites(
            competitionIds = repository.answer.results.mapTo(mutableSetOf()) { it.competition.id },
        )
        val model = viewModel()
        advanceUntilIdle()

        val shown = model.uiState.value.days.flatMap { it.events }
        assertTrue("the fixture must give more than one row for this to mean anything", shown.size > 1)
        // Everything recorded is ahead of this clock, so nothing has started and the listing
        // opens at its top — and, the point of the test, not at its bottom.
        assertEquals(shown.first().id, model.uiState.value.anchorId)
    }

    @Test
    fun `following nothing leaves no row to open on`() = runTest(dispatcher) {
        followed.value = Favorites(teamIds = setOf(aFollowedTeam))
        val model = viewModel()
        advanceUntilIdle()
        assertNotNull(model.uiState.value.anchorId)

        followed.value = Favorites.NONE
        advanceUntilIdle()

        assertNull(model.uiState.value.anchorId)
    }

    @Test
    fun `following nothing asks for nothing`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        assertEquals("a fresh install works before it has ever been online", 0, repository.calls)
        assertTrue(model.uiState.value.chosenNothing)
        assertEquals(emptyList<AgendaDay>(), model.uiState.value.days)
    }

    @Test
    fun `the first choice is what triggers the only load`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        followed.value = Favorites(teamIds = setOf(aFollowedTeam))
        advanceUntilIdle()

        assertEquals(1, repository.calls)
        assertFalse(model.uiState.value.chosenNothing)
        assertTrue(model.uiState.value.days.isNotEmpty())
    }

    @Test
    fun `following one more narrows what is already here rather than asking again`() = runTest(dispatcher) {
        val model = viewModel()
        followed.value = Favorites(teamIds = setOf(aFollowedTeam))
        advanceUntilIdle()
        val afterFirstLoad = repository.calls
        val shown = model.uiState.value.days.sumOf { it.events.size }

        val second = checkNotNull(repository.answer.results.last { it.visitor != null }.visitor).id
        followed.value = Favorites(teamIds = setOf(aFollowedTeam, second))
        advanceUntilIdle()

        assertEquals(afterFirstLoad, repository.calls)
        assertTrue(model.uiState.value.days.sumOf { it.events.size } >= shown)
    }

    @Test
    fun `only what the reader follows is shown`() = runTest(dispatcher) {
        val theirs = repository.answer.results.first { it.local != null }
        val theirTeam = checkNotNull(theirs.local)
        val model = viewModel()

        followed.value = Favorites(teamIds = setOf(theirTeam.id))
        advanceUntilIdle()

        val shown = model.uiState.value.days.flatMap { it.events }
        assertEquals("the page holds three events and one is theirs", 1, shown.size)
        assertEquals(theirTeam.name, shown.single().home?.name)
        assertTrue("nothing on this screen carries a mark", shown.none { it.favorite })
    }

    @Test
    fun `an event outside the three-day window is not shown`() = runTest(dispatcher) {
        val far = repository.answer.results.first().copy(
            id = 424_242,
            date = "2026-09-30T21:00:00+02:00",
        )
        repository.answer = repository.answer.copy(results = listOf(far))
        val model = viewModel()

        followed.value = Favorites(competitionIds = setOf(far.competition.id))
        advanceUntilIdle()

        assertEquals(1, repository.calls)
        assertTrue("a month away is not 'coming up'", model.uiState.value.days.isEmpty())
        assertTrue(model.uiState.value.nothingComingUp)
    }

    @Test
    fun `unfollowing everything clears the screen without asking anything`() = runTest(dispatcher) {
        val model = viewModel()
        followed.value = Favorites(teamIds = setOf(aFollowedTeam))
        advanceUntilIdle()
        val afterLoad = repository.calls

        followed.value = Favorites.NONE
        advanceUntilIdle()

        assertEquals(afterLoad, repository.calls)
        assertTrue(model.uiState.value.chosenNothing)
        assertEquals(emptyList<AgendaDay>(), model.uiState.value.days)
    }

    @Test
    fun `refreshing while following nothing never reaches the network`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        clock.advance(Duration.ofMinutes(10))
        model.onIntent(FavoritesIntent.Refresh)
        model.onIntent(FavoritesIntent.Resumed)
        advanceUntilIdle()

        assertEquals(0, repository.calls)
    }

    @Test
    fun `a failure leaves the last good answer with a banner`() = runTest(dispatcher) {
        val model = viewModel()
        followed.value = Favorites(teamIds = setOf(aFollowedTeam))
        advanceUntilIdle()
        val loaded = model.uiState.value.days

        repository.failure = ApiError.Offline
        clock.advance(Duration.ofSeconds(61))
        model.onIntent(FavoritesIntent.Resumed)
        advanceUntilIdle()

        val state = model.uiState.value
        assertEquals(loaded, state.days)
        assertEquals(ApiError.Offline, state.error)
        assertTrue(state.showingStale)
    }

    /**
     * The regression this screen shipped with: production holds far more than one page of
     * "today onwards", so reading only the first meant the window ended at teatime the same
     * day and everything followed tomorrow was quietly missing — while the site showed it.
     */
    @Test
    fun `the whole window is fetched, not only its first page`() = runTest(dispatcher) {
        val overleaf = repository.answer.results.first().copy(id = 909_090)
        repository.later[2] = repository.answer.copy(results = listOf(overleaf))
        val model = viewModel()

        followed.value = Favorites(competitionIds = setOf(overleaf.competition.id))
        advanceUntilIdle()

        assertEquals(2, repository.calls)
        val shown = model.uiState.value.days.flatMap { it.events }
        assertTrue("the event on page two is on screen", shown.any { it.id == overleaf.id })
    }

    @Test
    fun `the request is bounded to the window, widened a day each side`() = runTest(dispatcher) {
        followed.value = Favorites(teamIds = setOf(aFollowedTeam))
        viewModel()
        advanceUntilIdle()

        // now is 2026-08-29T21:00Z: three hours back is the 29th, three days on is the 1st.
        assertEquals(LocalDate.of(2026, 8, 28), repository.askedFrom)
        assertEquals(LocalDate.of(2026, 9, 2), repository.askedUntil)
    }

    /**
     * A walk that loses its tail would show a window with a silent gap at the end — the very
     * shape of the bug the walk fixes — so a page that never comes fails the whole load.
     */
    @Test
    fun `a page lost mid-walk fails the load rather than showing half a window`() = runTest(dispatcher) {
        val overleaf = repository.answer.results.first().copy(id = 909_090)
        repository.later[2] = repository.answer.copy(results = listOf(overleaf))
        repository.failOnPage = 2
        val model = viewModel()

        followed.value = Favorites(competitionIds = setOf(overleaf.competition.id))
        advanceUntilIdle()

        val state = model.uiState.value
        assertEquals(ApiError.Offline, state.error)
        assertFalse(state.loading)
        assertTrue("nothing pretends to be the window", state.days.isEmpty())
    }
}
