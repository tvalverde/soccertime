package es.mojon.soccertime.core.ui

import app.cash.turbine.test
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
import kotlinx.coroutines.delay
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

    private class Recording(answer: Page<EventDto>) : EventsRepository {
        val asks = mutableListOf<AgendaQuery>()
        var failure: ApiError? = null

        /** Set to fail only one of the two days a load asks for. */
        var failOn: String? = null
        var pageAnswer: Page<EventDto> = answer
        val perDay = mutableMapOf<String, Page<EventDto>>()

        /** Answers chosen by the whole query, so a filtered call can differ from a plain one. */
        var answerFor: (AgendaQuery) -> Page<EventDto>? = { null }

        /** How long each call takes, so one can be made to finish after another. */
        var takes: (AgendaQuery) -> Long = { 0 }

        override suspend fun upcoming(page: Int) = onDate(AgendaQuery(date = "", page = page))

        override suspend fun onDate(query: AgendaQuery): ApiResult<Page<EventDto>> {
            asks += query
            delay(takes(query))
            val failing = failure?.takeIf { failOn == null || failOn == query.date }
            return failing?.let { ApiResult.Failure(it) }
                ?: ApiResult.Success(answerFor(query) ?: perDay[query.date] ?: pageAnswer)
        }
    }

    /**
     * One load of the window is two requests, so counting requests no longer counts loads.
     * Today is the one that is never asked for newest-first.
     */
    private val Recording.loads: Int get() = asks.count { !it.newestFirst }

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

    /** A page of events at exactly the instants a test needs, built from the recorded one. */
    private fun pageOf(vararg dates: String): Page<EventDto> {
        val template = fixture().results.first()
        // Derived from the instant, so two days built by two calls cannot collide on an id —
        // which is exactly the clash the list would crash on, and therefore not one a test
        // may manufacture for itself.
        val events = dates.map { date ->
            template.copy(id = date.hashCode() and 0xFFFFFF, date = date, dateEnd = null)
        }
        return fixture().copy(count = events.size, next = null, results = events)
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

    /**
     * The window is yesterday and today, and the order is the whole design: today renders
     * while yesterday is still in flight, because today is where the reader is.
     */
    @Test
    fun `it opens on two days, and asks for today first`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        assertEquals(2, repository.asks.size)
        assertEquals("2026-08-30", repository.asks.first().date)
        assertEquals("2026-08-29", repository.asks.last().date)
        assertEquals(6, model.uiState.value.days.sumOf { it.events.size })
    }

    /**
     * A page holds a hundred and a busy day carries more, so asking yesterday in reading order
     * would spend the page on its small hours and drop the evening — the only part of it worth
     * showing at midnight, and the reason it is fetched at all.
     */
    @Test
    fun `yesterday is asked for from its end, and put back in reading order`() = runTest(dispatcher) {
        repository.perDay["2026-08-30"] = pageOf("2026-08-30T15:00:00Z")
        repository.perDay["2026-08-29"] = pageOf("2026-08-29T22:00:00Z", "2026-08-29T18:00:00Z")
        val model = viewModel()
        advanceUntilIdle()

        assertTrue("only yesterday is reversed", repository.asks.last().newestFirst)
        assertFalse(repository.asks.first().newestFirst)

        val shown = model.uiState.value.days.flatMap { day -> day.events.map { it.time } }
        assertEquals(listOf("20:00", "00:00", "17:00"), shown)
    }

    /**
     * Today is the part the reader came for. Losing the tail of the window is worth saying,
     * but not worth clearing the screen over.
     */
    @Test
    fun `yesterday failing leaves today standing`() = runTest(dispatcher) {
        repository.failure = ApiError.Offline
        repository.failOn = "2026-08-29"
        val model = viewModel()
        advanceUntilIdle()

        val state = model.uiState.value
        assertEquals(3, state.days.sumOf { it.events.size })
        assertEquals(ApiError.Offline, state.error)
    }

    /**
     * The path the first version got wrong. A refresh is a load whose query has not moved, so
     * "has the state changed" answers yes whether or not today came back — and yesterday was
     * then prepended onto a list that already held it. Two rows per event, duplicate keys in
     * the list, and a crash where the failure banner belonged.
     */
    @Test
    fun `a refresh whose today fails does not fetch yesterday a second time`() = runTest(dispatcher) {
        repository.perDay["2026-08-30"] = pageOf("2026-08-30T15:00:00Z")
        repository.perDay["2026-08-29"] = pageOf("2026-08-29T22:00:00Z")
        val model = viewModel()
        advanceUntilIdle()
        val whole = model.uiState.value.days.flatMap { it.events }
        assertEquals(2, whole.size)

        repository.failure = ApiError.Offline
        repository.failOn = "2026-08-30"
        clock.advance(Duration.ofSeconds(61))
        model.onIntent(AgendaIntent.Resumed)
        advanceUntilIdle()

        val after = model.uiState.value.days.flatMap { it.events }
        assertEquals("yesterday must not arrive twice", 2, after.size)
        assertEquals("and no two rows may share an id", 2, after.map { it.id }.distinct().size)
        assertEquals(ApiError.Offline, model.uiState.value.error)
    }

    @Test
    fun `today failing does not go on to ask for yesterday`() = runTest(dispatcher) {
        repository.failure = ApiError.RateLimited(retryAfterSeconds = 30)
        val model = viewModel()
        advanceUntilIdle()

        assertEquals("a second request would only earn a second 429", 1, repository.asks.size)
        assertEquals(ApiError.RateLimited(30), model.uiState.value.error)
    }

    /**
     * Where the listing opens. Not the first event still to start: one that began ninety
     * minutes ago is still on, and scrolling past it would hide what the reader turned the
     * television on for.
     */
    @Test
    fun `the listing opens on the first event that has not finished`() = runTest(dispatcher) {
        // Noon UTC. The first is over, the second is halfway through, the third is to come.
        repository.perDay["2026-08-30"] =
            pageOf("2026-08-30T09:00:00Z", "2026-08-30T11:00:00Z", "2026-08-30T15:00:00Z")
        repository.perDay["2026-08-29"] = pageOf()
        val model = viewModel()
        advanceUntilIdle()

        val opensOn = model.uiState.value.anchorId
        assertEquals(repository.perDay.getValue("2026-08-30").results[1].id, opensOn)
    }

    @Test
    fun `an anchor is not offered when every event in the window is over`() = runTest(dispatcher) {
        repository.perDay["2026-08-30"] = pageOf("2026-08-30T06:00:00Z")
        repository.perDay["2026-08-29"] = pageOf("2026-08-29T20:00:00Z")
        val model = viewModel()
        advanceUntilIdle()

        assertNull(model.uiState.value.anchorId)
    }

    /**
     * The window and the headings have to agree on which day it is. They did not: the headings
     * asked the device's zone and the window asked UTC, so in Spain between midnight and two
     * the agenda fetched the day before the one it was labelling — the very hours a two-day
     * window exists to cover.
     */
    @Test
    fun `the window is the reader's two days, not UTC's`() = runTest(dispatcher) {
        // 00:30 on the 31st in Madrid is still 22:30 on the 30th in UTC.
        clock = Movable(Instant.parse("2026-08-30T22:30:00Z"))
        val model = AgendaViewModel(
            events = repository,
            presenter = EventPresenter(EventTimes(clock = clock, zone = ZoneId.of("Europe/Madrid"))),
            clock = clock,
            favorites = followed,
        )
        advanceUntilIdle()

        assertEquals(listOf("2026-08-31", "2026-08-30"), repository.asks.map { it.date })
        assertEquals(LocalDate.of(2026, 8, 31), model.uiState.value.day)
    }

    @Test
    fun `narrowing to a followed team is a filter the server applies, to both days`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        model.onIntent(
            AgendaIntent.Narrow(AgendaFilter(42, "Argentina", null, FollowableKind.Teams)),
        )
        advanceUntilIdle()

        val forTheFilter = repository.asks.takeLast(2)
        assertEquals(listOf(42, 42), forTheFilter.map { it.team })
        assertEquals(listOf(null, null), forTheFilter.map { it.competition })
        assertEquals("Argentina", model.uiState.value.filter?.name)
    }

    @Test
    fun `a competition narrows on the other parameter, because the API has two`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()

        model.onIntent(
            AgendaIntent.Narrow(AgendaFilter(7, "FIBA Copa Mundial", null, FollowableKind.Competitions)),
        )
        advanceUntilIdle()

        assertEquals(7, repository.asks.last().competition)
        assertNull(repository.asks.last().team)
    }

    /**
     * Pressing a followed team while the plain agenda is still loading.
     *
     * `collectLatest` cancels the load it replaces, but a cancellation that is caught and
     * turned into a result is not a cancellation: the abandoned load went on to publish its
     * own answer, and whichever finished last won. On the television that looked like the
     * filtered agenda appearing and then, seconds later, reloading itself back to everything.
     */
    @Test
    fun `a filter is not overwritten by the load it replaced`() = runTest(dispatcher) {
        val barcelona = AgendaFilter(42, "FC Barcelona", null, FollowableKind.Teams)
        repository.answerFor = { query ->
            when {
                // Yesterday has nothing to add either way; today is what the two loads differ on.
                query.newestFirst -> pageOf()
                query.team == barcelona.id -> pageOf("2026-08-30T18:00:00Z")
                else -> pageOf("2026-08-30T15:00:00Z")
            }
        }
        // The plain load is still in flight, and will answer well after the filtered one.
        repository.takes = { query -> if (query.team == null) 5_000 else 10 }

        val model = viewModel()
        advanceTimeBy(100)
        model.onIntent(AgendaIntent.Narrow(barcelona))
        advanceUntilIdle()

        val shown = model.uiState.value.days.flatMap { day -> day.events.map { it.time } }
        assertEquals("only the filtered answer may be on screen", listOf("20:00"), shown)
        assertEquals(barcelona, model.uiState.value.filter)
        assertNull("an abandoned load is not a failure to report", model.uiState.value.error)
    }

    /**
     * Leaving one followed thing for another.
     *
     * Re-entering the agenda asks it to refresh, and a refresh reloaded whatever was last
     * loaded rather than what is being shown now — in its own coroutine, outside the single
     * flight the query pipeline gives. So the old filter's window was fetched alongside the
     * new one and its yesterday prepended onto it: the header said MotoGP, the count said
     * MotoGP, and a Barcelona match sat above them under AYER.
     */
    @Test
    fun `a refresh reloads what is on screen, not what used to be`() = runTest(dispatcher) {
        val barcelona = AgendaFilter(42, "FC Barcelona", null, FollowableKind.Teams)
        val motogp = AgendaFilter(7, "MotoGP", null, FollowableKind.Competitions)
        repository.answerFor = { query ->
            when {
                query.team == barcelona.id -> pageOf("2026-08-29T21:00:00Z")
                query.competition == motogp.id -> pageOf("2026-08-30T13:00:00Z")
                else -> pageOf()
            }
        }
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.Narrow(barcelona))
        advanceUntilIdle()

        // The window the reader is leaving answers slowly, as a real one does, so a reload of
        // it would land after the window they asked for.
        repository.takes = { query -> if (query.team == barcelona.id) 3_000 else 10 }
        model.onIntent(AgendaIntent.Narrow(motogp))
        clock.advance(Duration.ofSeconds(61))
        model.onIntent(AgendaIntent.Resumed)
        advanceUntilIdle()

        val shown = model.uiState.value.days.flatMap { it.events }
        assertTrue(
            "nothing from the filter that was left behind may remain",
            shown.none { it.competition == "La Liga EA Sports" },
        )
        assertEquals(motogp, model.uiState.value.filter)
        assertNull("the refresh must carry the filter that is on screen", repository.asks.last().team)
        assertEquals(motogp.id, repository.asks.last().competition)
    }

    @Test
    fun `clearing the filter asks for the whole window again`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.Narrow(AgendaFilter(42, "Argentina", null, FollowableKind.Teams)))
        advanceUntilIdle()

        model.onIntent(AgendaIntent.Narrow(null))
        advanceUntilIdle()

        assertNull(repository.asks.last().team)
        assertNull(model.uiState.value.filter)
    }

    @Test
    fun `typing a word costs one request, not one per letter`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val before = repository.loads

        val word = "Barcelona"
        word.indices.forEach { index ->
            model.onIntent(AgendaIntent.Search(word.take(index + 1)))
            advanceTimeBy(50.milliseconds)
        }
        advanceUntilIdle()

        assertEquals(1, repository.loads - before)
        assertEquals(word, repository.asks.last().search)
    }

    @Test
    fun `a single letter is not a search and costs nothing`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val before = repository.loads

        model.onIntent(AgendaIntent.Search("B"))
        advanceUntilIdle()

        assertEquals(0, repository.loads - before)
        assertEquals("B", model.uiState.value.query)
    }

    @Test
    fun `clearing the box asks for the unfiltered day again`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.Search("Barcelona"))
        advanceUntilIdle()
        val before = repository.loads

        model.onIntent(AgendaIntent.Search(""))
        advanceUntilIdle()

        assertEquals(1, repository.loads - before)
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
        val loaded = repository.loads

        clock.advance(Duration.ofSeconds(4))
        repeat(5) { model.onIntent(AgendaIntent.Refresh) }
        advanceUntilIdle()

        assertEquals("four seconds on, the answer cannot have changed", loaded, repository.loads)
    }

    @Test
    fun `a refresh after five seconds does ask`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = repository.loads

        clock.advance(Duration.ofSeconds(6))
        model.onIntent(AgendaIntent.Refresh)
        advanceUntilIdle()

        assertEquals(loaded + 1, repository.loads)
    }

    @Test
    fun `coming back to a fresh screen does not reload it`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = repository.loads

        clock.advance(Duration.ofSeconds(30))
        model.onIntent(AgendaIntent.Resumed)
        advanceUntilIdle()

        assertEquals(loaded, repository.loads)
    }

    @Test
    fun `coming back to one over a minute old reloads it`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = repository.loads

        clock.advance(Duration.ofSeconds(61))
        model.onIntent(AgendaIntent.Resumed)
        advanceUntilIdle()

        assertEquals(loaded + 1, repository.loads)
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
        model.onIntent(AgendaIntent.Narrow(AgendaFilter(42, "Argentina", null, FollowableKind.Teams)))
        advanceUntilIdle()

        val state = model.uiState.value
        assertEquals(emptyList<AgendaDay>(), state.days)
        assertEquals(ApiError.RateLimited(12), state.error)
        assertFalse("stale would be a lie: this is a different listing", state.showingStale)
    }

    @Test
    fun `following a team re-marks the rows without asking the server again`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        val loaded = repository.loads
        val everyRow = model.uiState.value.days.flatMap { it.events }
        assertTrue("nothing is marked yet", everyRow.none { it.favorite })

        val aTeamOnScreen = checkNotNull(repository.pageAnswer.results.first { it.local != null }.local).id
        followed.value = Favorites(teamIds = setOf(aTeamOnScreen))
        advanceUntilIdle()

        assertEquals("marking is a redraw, not a request", loaded, repository.loads)
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
