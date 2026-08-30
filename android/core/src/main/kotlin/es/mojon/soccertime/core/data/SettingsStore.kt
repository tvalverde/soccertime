package es.mojon.soccertime.core.data

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.stringPreferencesKey
import java.io.IOException
import kotlin.time.Duration.Companion.seconds
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.retryWhen

/**
 * How large the phone draws its text.
 *
 * Three fixed steps rather than a free slider, because the choice being offered is "a bit
 * smaller, as designed, a bit larger" and a slider would offer three hundred answers to a
 * question with three. [MEDIUM] is exactly the size every screen was designed at, so choosing
 * it changes nothing — which is what makes it the default.
 *
 * The factor multiplies the density's `fontScale`, so it composes with the system's own
 * accessibility setting instead of fighting it.
 */
enum class FontScale(val factor: Float) {
    SMALL(0.9f),
    MEDIUM(1f),
    LARGE(1.15f),
}

/**
 * Reader preferences, kept on this device in their own file beside the favourites.
 *
 * The same resilience rule as [FavoritesStore]: a read failure yields the default and looks
 * again, because a busy disk should cost one default reading — never a crash, and never a
 * collector that silently stops reacting for the life of the process.
 */
class SettingsStore(private val store: DataStore<Preferences>) {

    val fontScale: Flow<FontScale> =
        store.data
            .retryWhen { cause, _ ->
                if (cause !is IOException) return@retryWhen false
                emit(emptyPreferences())
                delay(RETRY_DELAY)
                true
            }
            .map { stored -> stored[FONT_SCALE].asFontScale() }
            .distinctUntilChanged()

    suspend fun setFontScale(scale: FontScale) {
        store.edit { it[FONT_SCALE] = scale.name }
    }

    companion object {
        const val FILE_NAME = "settings"

        private val FONT_SCALE = stringPreferencesKey("font_scale")
        private val RETRY_DELAY = 1.seconds

        /** A value written by a future version this build does not know reads as the default. */
        private fun String?.asFontScale(): FontScale =
            FontScale.entries.firstOrNull { it.name == this } ?: FontScale.MEDIUM
    }
}
