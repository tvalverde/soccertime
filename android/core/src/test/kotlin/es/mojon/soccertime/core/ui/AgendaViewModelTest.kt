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
import java.time.YearMonth
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

        override suspend fun upcoming(from: LocalDate, until: LocalDate, page: Int) =
            onDate(AgendaQuery(date = "", page = page))

        val dayAsks = mutableListOf<Triple<LocalDate, Int?, Int?>>()
        var litAnswer: List<LocalDate> = emptyList()
        var litFailure: ApiError? = null

        override suspend fun days(
            from: LocalDate,
            until: LocalDate,
            team: Int?,
            competition: Int?,
        ): ApiResult<List<LocalDate>> {
            dayAsks += Triple(from, team, competition)
            return litFailure?.let { ApiResult.Failure(it) } ?: ApiResult.Success(litAnswer)
        }

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

    /** Where the listing opens: the last row that has started, across both days of the window. */
    @Test
    fun `the listing opens on the last event that has started`() = runTest(dispatcher) {
        // Noon UTC. The 11:00 has begun and the 15:00 has not; the 09:00 used to win.
        repository.perDay["2026-08-30"] =
            pageOf("2026-08-30T09:00:00Z", "2026-08-30T11:00:00Z", "2026-08-30T15:00:00Z")
        repository.perDay["2026-08-29"] = pageOf()
        val model = viewModel()
        advanceUntilIdle()

        val opensOn = model.uiState.value.anchorId
        assertEquals(repository.perDay.getValue("2026-08-30").results[1].id, opensOn)
    }

    /** Four in the morning. Everything is over, and the most recent of it is still the answer. */
    @Test
    fun `a window entirely in the past opens on its most recent event`() = runTest(dispatcher) {
        repository.perDay["2026-08-30"] = pageOf("2026-08-30T06:00:00Z")
        repository.perDay["2026-08-29"] = pageOf("2026-08-29T20:00:00Z")
        val model = viewModel()
        advanceUntilIdle()

        assertEquals(
            repository.perDay.getValue("2026-08-30").results.single().id,
            model.uiState.value.anchorId,
        )
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
    fun `narrowing to a followed team is a filter the server applies, in one open-ended ask`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        repository.asks.clear()

        model.onIntent(
            AgendaIntent.Narrow(AgendaFilter(42, "Argentina", null, FollowableKind.Teams)),
        )
        advanceUntilIdle()

        val ask = repository.asks.single()
        assertEquals(42, ask.team)
        assertNull(ask.competition)
        assertEquals("everything from here onward, not a window", "2026-08-30", ask.dateFrom)
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

    /**
     * Narrowing, and asking for another page before the narrowed listing has arrived.
     *
     * `loadedFor` and `nextPage` still describe the listing on its way out, so its next page
     * belongs to a list about to be discarded. The generation cannot catch this alone: the
     * replacement claimed the number before the page was even asked for, so both agree.
     */
    @Test
    fun `a page of the listing being replaced never joins the new one`() = runTest(dispatcher) {
        val barcelona = AgendaFilter(42, "FC Barcelona", null, FollowableKind.Teams)
        repository.pageAnswer = repository.pageAnswer.copy(next = "https://www.mojon.es/…?page=2")
        val model = viewModel()
        advanceUntilIdle()
        assertTrue(model.uiState.value.canLoadMore)

        repository.answerFor = { query ->
            when {
                query.newestFirst -> pageOf()
                query.page == 2 -> pageOf("2026-08-30T23:00:00Z")
                query.team == barcelona.id -> pageOf("2026-08-30T18:00:00Z")
                else -> pageOf()
            }
        }
        // The page answers slowly, so it would land after the listing it does not belong to
        // has already replaced what was on screen.
        repository.takes = { query -> if (query.page == 2) 3_000 else 10 }

        // Narrow first, then ask for another page while that is still in the air. The page
        // is a page of the listing being thrown away — `loadedFor` still names it — and it
        // has nothing to do with what the reader is now looking at.
        model.onIntent(AgendaIntent.Narrow(barcelona))
        advanceTimeBy(1)
        model.onIntent(AgendaIntent.LoadMore)
        advanceUntilIdle()

        val shown = model.uiState.value.days.flatMap { day -> day.events.map { it.time } }
        assertEquals("only the filtered listing may be on screen", listOf("20:00"), shown)
    }

    /**
     * Nothing marked a page as being on its way: the page number only advanced when a page
     * *arrived*, and the button stayed live meanwhile. Two presses on a slow connection
     * fetched the same page twice and appended it twice — and a list keyed by event id does
     * not survive the same id appearing on it twice; it throws, and the app goes with it.
     */
    @Test
    fun `pressing for another page twice does not fetch it twice`() = runTest(dispatcher) {
        repository.pageAnswer = repository.pageAnswer.copy(next = "https://www.mojon.es/…?page=2")
        // Yesterday empty from the start, so the only way an id can repeat on this listing is
        // the page arriving twice.
        repository.perDay["2026-08-29"] = pageOf()
        val model = viewModel()
        advanceUntilIdle()
        val asked = repository.asks.size
        repository.answerFor = { query ->
            if (query.page == 2) pageOf("2026-08-30T23:00:00Z") else null
        }
        repository.takes = { query -> if (query.page == 2) 3_000 else 0 }

        model.onIntent(AgendaIntent.LoadMore)
        model.onIntent(AgendaIntent.LoadMore)
        advanceUntilIdle()

        assertEquals("the second press must buy nothing", 1, repository.asks.size - asked)
        val ids = model.uiState.value.days.flatMap { day -> day.events.map { it.id } }
        assertEquals("and no id may appear twice", ids.size, ids.distinct().size)
    }

    /**
     * The banner offers Retry, and Retry did nothing at all: the guard that stops a refresh
     * before anything has loaded read a field only ever written on success, so once the very
     * first load had failed there was no way back except changing the search or the filter.
     */
    @Test
    fun `retry works after the first load of all failed`() = runTest(dispatcher) {
        repository.failure = ApiError.Offline
        val model = viewModel()
        advanceUntilIdle()
        val asked = repository.asks.size
        assertEquals(ApiError.Offline, model.uiState.value.error)

        repository.failure = null
        model.onIntent(AgendaIntent.Refresh)
        advanceUntilIdle()

        assertTrue("Retry must actually ask again", repository.asks.size > asked)
        assertTrue(model.uiState.value.days.isNotEmpty())
        assertNull(model.uiState.value.error)
    }

    /**
     * Following something re-marks the rows already in hand without asking the server. When a
     * narrowed load had failed, the events it cleared from the screen were still held behind
     * it — so that redraw put the whole plain agenda back, under the followed team's chip,
     * with the failure banner still on it.
     */
    @Test
    fun `a failed narrowing cannot be undone by following something`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        assertTrue(model.uiState.value.days.isNotEmpty())

        repository.failure = ApiError.Offline
        model.onIntent(AgendaIntent.Narrow(AgendaFilter(42, "FC Barcelona", null, FollowableKind.Teams)))
        advanceUntilIdle()
        assertEquals(emptyList<AgendaDay>(), model.uiState.value.days)

        followed.value = Favorites(teamIds = setOf(42))
        advanceUntilIdle()

        assertEquals(
            "nothing may come back that the failure took away",
            emptyList<AgendaDay>(),
            model.uiState.value.days,
        )
    }

    /**
     * A television is left composed for days. Held once at construction, the window was
     * whatever day the view model was born on — so the morning after, it went on fetching
     * yesterday and the day before, under headings naming a date that had moved on.
     */
    @Test
    fun `the window follows the day, not the day the screen was built on`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        assertEquals(LocalDate.of(2026, 8, 30), model.uiState.value.day)

        clock.advance(Duration.ofHours(24))
        model.onIntent(AgendaIntent.Resumed)
        advanceUntilIdle()

        assertEquals(listOf("2026-08-31", "2026-08-30"), repository.asks.takeLast(2).map { it.date })
        assertEquals(LocalDate.of(2026, 8, 31), model.uiState.value.day)
    }

    /**
     * The television keeps this view model while the agenda is off screen, so coming back to it
     * through the rail painted the chip and the rows of the followed team just left, under a
     * screen that no longer said why. The listing has to go when the filter does, not when its
     * replacement arrives seconds later.
     */
    @Test
    fun `narrowing drops the listing it is leaving, at once`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        assertTrue(model.uiState.value.days.isNotEmpty())

        val barcelona = AgendaFilter(42, "FC Barcelona", null, FollowableKind.Teams)
        model.onIntent(AgendaIntent.Narrow(barcelona))
        // Deliberately not advanced: "at once" means before anything has had a chance to run.

        val state = model.uiState.value
        assertEquals(emptyList<AgendaDay>(), state.days)
        assertNull(state.anchorId)
        assertEquals(0, state.count)
        assertFalse(state.canLoadMore)
        assertTrue("and it says so, rather than showing nothing in silence", state.loading)
        assertEquals(barcelona, state.filter)
    }

    /**
     * Both apps re-dispatch the filter every time the agenda re-enters composition, with the
     * same value. The `StateFlow` deduplicates that into no reload, but the clearing above
     * would not deduplicate itself — so switching to the Agenda tab would blank a screen that
     * was already showing exactly what was asked for.
     */
    @Test
    fun `the same filter arriving again leaves a loaded screen alone`() = runTest(dispatcher) {
        val barcelona = AgendaFilter(42, "FC Barcelona", null, FollowableKind.Teams)
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.Narrow(barcelona))
        advanceUntilIdle()
        val onScreen = model.uiState.value.days
        assertTrue(onScreen.isNotEmpty())

        // A different instance carrying the same filter, which is what re-entry produces.
        model.onIntent(AgendaIntent.Narrow(barcelona.copy()))

        assertEquals(onScreen, model.uiState.value.days)
        assertFalse("nor may it claim to be loading", model.uiState.value.loading)
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

    @Test
    fun `a day chosen on the calendar is one request, for that day alone`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        repository.asks.clear()

        model.onIntent(AgendaIntent.PickDay(LocalDate.of(2026, 9, 5)))
        advanceUntilIdle()

        // No yesterday: "the evening before it" is a courtesy the present deserves and an
        // arbitrary Saturday does not.
        assertEquals(listOf("2026-09-05"), repository.asks.map { it.date })
        assertFalse(repository.asks.single().newestFirst)
        assertEquals(LocalDate.of(2026, 9, 5), model.uiState.value.chosenDay)
    }

    @Test
    fun `clearing the chosen day returns to yesterday and today`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.PickDay(LocalDate.of(2026, 9, 5)))
        advanceUntilIdle()
        repository.asks.clear()

        model.onIntent(AgendaIntent.PickDay(null))
        advanceUntilIdle()

        assertEquals(listOf("2026-08-30", "2026-08-29"), repository.asks.map { it.date })
        assertNull(model.uiState.value.chosenDay)
    }

    @Test
    fun `an exhausted day offers tomorrow, and pulling appends it under its own heading`() = runTest(dispatcher) {
        repository.perDay["2026-08-30"] = pageOf("2026-08-30T18:00:00+02:00")
        repository.perDay["2026-08-29"] = pageOf("2026-08-29T21:00:00+02:00")
        repository.perDay["2026-08-31"] = pageOf("2026-08-31T12:00:00+02:00", "2026-08-31T20:00:00+02:00")
        val model = viewModel()
        advanceUntilIdle()

        assertTrue(
            "the foot is already worded",
            model.uiState.value.nextDayLabel.orEmpty().contains("MAÑANA"),
        )
        repository.asks.clear()

        model.onIntent(AgendaIntent.LoadNextDay)
        advanceUntilIdle()

        assertEquals(listOf("2026-08-31"), repository.asks.map { it.date })
        val days = model.uiState.value.days
        assertEquals(3, days.size)
        assertEquals(2, days.last().events.size)
        // The foot moves on with the window's end.
        assertFalse(model.uiState.value.nextDayLabel.orEmpty().contains("MAÑANA"))
    }

    @Test
    fun `tomorrow is not reachable past an unshown tail of today`() = runTest(dispatcher) {
        // The recorded page carries `next`, so more of today remains unshown.
        val model = viewModel()
        advanceUntilIdle()
        assertTrue(model.uiState.value.canLoadMore)
        repository.asks.clear()

        model.onIntent(AgendaIntent.LoadNextDay)
        advanceUntilIdle()

        assertEquals(emptyList<AgendaQuery>(), repository.asks)
    }

    @Test
    fun `with a chosen day, pulling moves to the next one instead of growing`() = runTest(dispatcher) {
        repository.perDay["2026-09-05"] = pageOf("2026-09-05T18:00:00+02:00")
        repository.perDay["2026-09-06"] = pageOf("2026-09-06T18:00:00+02:00")
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.PickDay(LocalDate.of(2026, 9, 5)))
        advanceUntilIdle()
        repository.asks.clear()

        model.onIntent(AgendaIntent.LoadNextDay)
        advanceUntilIdle()

        assertEquals(listOf("2026-09-06"), repository.asks.map { it.date })
        assertEquals(LocalDate.of(2026, 9, 6), model.uiState.value.chosenDay)
        assertEquals(1, model.uiState.value.days.size)
    }

    private val newey = AgendaFilter(7, "Racing", null, FollowableKind.Teams)

    @Test
    fun `narrowed to a team, the listing is open-ended and yesterday stays out`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        repository.asks.clear()

        model.onIntent(AgendaIntent.Narrow(newey))
        advanceUntilIdle()

        val ask = repository.asks.single()
        assertNull("no single day: everything from here onward", ask.date)
        assertEquals("2026-08-30", ask.dateFrom)
        assertEquals(7, ask.team)
        assertNull("no foot: there is no frontier to cross", model.uiState.value.nextDayLabel)
    }

    @Test
    fun `narrowed, a chosen day moves where the listing starts`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.Narrow(newey))
        advanceUntilIdle()
        repository.asks.clear()

        model.onIntent(AgendaIntent.PickDay(LocalDate.of(2026, 9, 12)))
        advanceUntilIdle()

        assertEquals("2026-09-12", repository.asks.single().dateFrom)
        assertEquals(LocalDate.of(2026, 9, 12), model.uiState.value.chosenDay)
    }

    @Test
    fun `a month is peeked once, and its lit days arrive under the narrowing`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.Narrow(newey))
        advanceUntilIdle()
        repository.litAnswer = listOf(LocalDate.of(2026, 9, 12), LocalDate.of(2026, 9, 19))

        model.onIntent(AgendaIntent.PeekMonth(YearMonth.of(2026, 9)))
        model.onIntent(AgendaIntent.PeekMonth(YearMonth.of(2026, 9)))
        advanceUntilIdle()

        assertEquals(1, repository.dayAsks.size)
        assertEquals(7, repository.dayAsks.single().second)
        assertEquals(setOf(LocalDate.of(2026, 9, 12), LocalDate.of(2026, 9, 19)), model.uiState.value.litDays)
        assertTrue(YearMonth.of(2026, 9) in model.uiState.value.litMonths)
    }

    @Test
    fun `a failed peek leaves the month unknown, and therefore fully pressable`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        repository.litFailure = ApiError.Offline

        model.onIntent(AgendaIntent.PeekMonth(YearMonth.of(2026, 9)))
        advanceUntilIdle()

        assertTrue(model.uiState.value.litMonths.isEmpty())
        // Known again once the network is back: the month may be asked for anew.
        repository.litFailure = null
        repository.litAnswer = listOf(LocalDate.of(2026, 9, 5))
        model.onIntent(AgendaIntent.PeekMonth(YearMonth.of(2026, 9)))
        advanceUntilIdle()
        assertTrue(LocalDate.of(2026, 9, 5) in model.uiState.value.litDays)
    }

    @Test
    fun `choosing the day already shown asks for nothing`() = runTest(dispatcher) {
        val model = viewModel()
        advanceUntilIdle()
        model.onIntent(AgendaIntent.PickDay(LocalDate.of(2026, 9, 5)))
        advanceUntilIdle()
        repository.asks.clear()

        model.onIntent(AgendaIntent.PickDay(LocalDate.of(2026, 9, 5)))
        advanceUntilIdle()

        assertEquals(emptyList<AgendaQuery>(), repository.asks)
    }
}
