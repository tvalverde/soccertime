package es.mojon.soccertime.core

import android.content.Context
import es.mojon.soccertime.core.data.EventsRepository
import es.mojon.soccertime.core.network.Network
import java.io.File

/**
 * Everything the two applications share, built once.
 *
 * Six objects with no cycles between them do not need a dependency-injection framework; they
 * need one place that says what depends on what, which is this. Each application holds one of
 * these on its `Application`.
 */
class AppGraph(
    cacheDirectory: File?,
    baseUrl: String = BuildConfig.API_BASE_URL,
) {
    val client = Network.okHttp(cacheDirectory)
    val api = Network.api(baseUrl, client)
    val events = EventsRepository(api)

    companion object {
        fun from(context: Context): AppGraph =
            AppGraph(cacheDirectory = File(context.cacheDir, HTTP_CACHE_DIRECTORY))

        private const val HTTP_CACHE_DIRECTORY = "http"
    }
}
