package es.mojon.soccertime.core

import android.content.Context
import androidx.datastore.preferences.preferencesDataStore
import es.mojon.soccertime.core.data.ApiEventsRepository
import es.mojon.soccertime.core.data.FavoritesStore
import es.mojon.soccertime.core.network.Network
import es.mojon.soccertime.core.time.EventTimes
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
    val favorites: FavoritesStore,
    baseUrl: String = BuildConfig.API_BASE_URL,
) {
    val client = Network.okHttp(cacheDirectory)
    val api = Network.api(baseUrl, client)
    val events = ApiEventsRepository(api)

    /** Reads the device's own zone and clock; both are arguments so tests can fix them. */
    val times = EventTimes()

    companion object {
        fun from(context: Context): AppGraph =
            AppGraph(
                cacheDirectory = File(context.cacheDir, HTTP_CACHE_DIRECTORY),
                favorites = FavoritesStore(context.applicationContext.favoritesStore),
            )

        private const val HTTP_CACHE_DIRECTORY = "http"
    }
}

/**
 * The delegate rather than a factory call, because `DataStore` refuses to have two instances
 * alive on one file and throws on first use when it does. This makes one per process by
 * construction — the application context is what it is read from, so an activity being
 * recreated cannot produce a second.
 */
private val Context.favoritesStore by preferencesDataStore(name = FavoritesStore.FILE_NAME)
