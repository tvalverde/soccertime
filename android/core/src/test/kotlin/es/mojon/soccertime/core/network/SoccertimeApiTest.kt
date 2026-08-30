package es.mojon.soccertime.core.network

import es.mojon.soccertime.core.network.SoccertimeApi.Companion.MAX_PAGE_SIZE
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import okhttp3.OkHttpClient
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * What the client does with the answers the API gives that are not a page of events.
 *
 * The interesting ones are the refusals. Two different things refuse a caller here — the
 * application at thirty requests a minute and Traefik at sixty — and they disagree about the
 * body: one sends JSON and the other plain text. A client that read the body to find out how
 * long to wait would work against one of them and fail against the other, which is why the
 * header is what these tests pin.
 */
class SoccertimeApiTest {

    private lateinit var server: MockWebServer
    private lateinit var api: SoccertimeApi

    @Before
    fun start() {
        server = MockWebServer()
        server.start()
        api = Network.api(server.url("/soccertime/api/v1/").toString(), OkHttpClient())
    }

    @After
    fun stop() {
        server.close()
    }

    private fun fixture(name: String): String =
        checkNotNull(javaClass.classLoader?.getResourceAsStream("fixtures/$name")).use {
            it.readBytes().decodeToString()
        }

    private fun json(code: Int, body: String) =
        MockResponse.Builder()
            .code(code)
            .setHeader("Content-Type", "application/json")
            .body(body)
            .build()

    private suspend fun events(page: Int?) =
        safeCall {
            api.events(
                date = "2026-08-30",
                dateFrom = null,
                dateTo = null,
                search = null,
                watchable = null,
                team = null,
                competition = null,
                ordering = null,
                page = page,
                pageSize = MAX_PAGE_SIZE,
            )
        }

    /**
     * A caller that walked away is not a caller that failed.
     *
     * `CancellationException` is an `Exception`, so the catch-all here used to turn it into a
     * result — and a coroutine whose cancellation is caught does not stop. It carried on and
     * published an answer for a screen that had moved on, which on the television looked like
     * a filtered agenda reloading itself back to the whole one a few seconds after it appeared.
     */
    @Test
    fun `an abandoned call is abandoned, not reported as a failure`() = runTest {
        var answered: ApiResult<Unit>? = null

        val walkedAway = launch { answered = safeCall { awaitCancellation() } }
        advanceUntilIdle()
        walkedAway.cancelAndJoin()

        assertNull("a call nobody is waiting for must produce no result at all", answered)
    }

    @Test
    fun `a page comes back parsed and the query carries every filter that was set`() = runTest {
        server.enqueue(json(200, fixture("events_day_page1.json")))

        val result = events(page = 2)

        assertTrue(result is ApiResult.Success)
        assertEquals(3, (result as ApiResult.Success).value.results.size)

        val asked = server.takeRequest().target
        assertTrue(asked, asked.startsWith("/soccertime/api/v1/events/"))
        assertTrue(asked, asked.contains("date=2026-08-30"))
        assertTrue(asked, asked.contains("page=2"))
        assertTrue(asked, asked.contains("page_size=$MAX_PAGE_SIZE"))
        // A null filter is left out of the query rather than sent empty.
        assertTrue(asked, !asked.contains("search"))
        assertTrue(asked, !asked.contains("watchable"))
    }

    @Test
    fun `a page past the end is a plain 404 and not a crash`() = runTest {
        server.enqueue(json(404, fixture("events_past_the_end.json")))

        val result = events(page = 999)

        assertEquals(ApiError.Http(404), (result as ApiResult.Failure).error)
    }

    @Test
    fun `the proxy refuses with plain text and the wait still comes from the header`() = runTest {
        server.enqueue(
            MockResponse.Builder()
                .code(429)
                .setHeader("Content-Type", "text/plain; charset=utf-8")
                .setHeader("Retry-After", "17")
                .body("Too Many Requests")
                .build(),
        )

        val result = events(page = null)

        assertEquals(ApiError.RateLimited(17L), (result as ApiResult.Failure).error)
    }

    @Test
    fun `the application refuses with json and the wait still comes from the header`() = runTest {
        server.enqueue(
            MockResponse.Builder()
                .code(429)
                .setHeader("Content-Type", "application/json")
                .setHeader("Retry-After", "42")
                .body("""{"detail":"Request was throttled. Expected available in 42 seconds."}""")
                .build(),
        )

        val result = events(page = null)

        assertEquals(ApiError.RateLimited(42L), (result as ApiResult.Failure).error)
    }

    @Test
    fun `a refusal with no header leaves the wait unknown rather than guessed`() = runTest {
        server.enqueue(MockResponse.Builder().code(429).body("Too Many Requests").build())

        val result = events(page = null)

        assertEquals(ApiError.RateLimited(null), (result as ApiResult.Failure).error)
    }

    @Test
    fun `a wait too long to be one is left unknown rather than shown`() = runTest {
        // Past `Int.MAX_VALUE`. The screens narrow this to an Int to pick a plural, so a value
        // that wraps would choose the wording for zero while printing four billion seconds.
        server.enqueue(MockResponse.Builder().code(429).setHeader("Retry-After", "4294967296").build())

        val result = events(page = null)

        assertEquals(ApiError.RateLimited(null), (result as ApiResult.Failure).error)
    }

    @Test
    fun `an hour is still read, and the second past it is not`() = runTest {
        server.enqueue(MockResponse.Builder().code(429).setHeader("Retry-After", "3600").build())
        server.enqueue(MockResponse.Builder().code(429).setHeader("Retry-After", "3601").build())

        val inside = events(page = null)
        val outside = events(page = null)

        assertEquals(ApiError.RateLimited(3600L), (inside as ApiResult.Failure).error)
        assertEquals(ApiError.RateLimited(null), (outside as ApiResult.Failure).error)
    }

    @Test
    fun `a negative wait is not a wait`() = runTest {
        server.enqueue(MockResponse.Builder().code(429).setHeader("Retry-After", "-1").build())

        val result = events(page = null)

        assertEquals(ApiError.RateLimited(null), (result as ApiResult.Failure).error)
    }

    @Test
    fun `a bad filter comes back naming the parameter it could not read`() = runTest {
        server.enqueue(json(400, fixture("error_400_bad_date.json")))

        val result = events(page = null)

        val error = (result as ApiResult.Failure).error as ApiError.BadRequest
        assertTrue(error.message, error.message.startsWith("date: "))
        assertTrue(error.message, error.message.contains("YYYY-MM-DD"))
    }

    @Test
    fun `a 400 that is not json falls back to a message rather than a parse failure`() = runTest {
        server.enqueue(
            MockResponse.Builder()
                .code(400)
                .setHeader("Content-Type", "text/html")
                .body("<html>Bad Request</html>")
                .build(),
        )

        val result = events(page = null)

        assertTrue((result as ApiResult.Failure).error is ApiError.BadRequest)
    }

    @Test
    fun `nothing listening is offline and not an unexpected failure`() = runTest {
        server.close()

        val result = events(page = null)

        assertEquals(ApiError.Offline, (result as ApiResult.Failure).error)
    }

    @Test
    fun `a repeat request revalidates against the etag instead of downloading again`() = runTest {
        val cacheDirectory = createTempDirectory()
        val client = Network.okHttp(cacheDirectory)
        val cached = Network.api(server.url("/soccertime/api/v1/").toString(), client)
        val body = fixture("events_day_page1.json")

        server.enqueue(
            MockResponse.Builder()
                .code(200)
                .setHeader("Content-Type", "application/json")
                .setHeader("ETag", "\"v1\"")
                .setHeader("Cache-Control", "max-age=0")
                .body(body)
                .build(),
        )
        server.enqueue(MockResponse.Builder().code(304).setHeader("ETag", "\"v1\"").build())

        repeat(2) {
            val page = cached.events("2026-08-30", null, null, null, null, null, null, null, null, MAX_PAGE_SIZE)
            assertEquals(3, page.results.size)
        }

        server.takeRequest()
        val revalidation = server.takeRequest()
        assertEquals("\"v1\"", revalidation.headers["If-None-Match"])
        assertEquals(1, client.cache?.hitCount())
    }

    private fun createTempDirectory() =
        java.nio.file.Files.createTempDirectory("okhttp-cache").toFile().apply { deleteOnExit() }
}
