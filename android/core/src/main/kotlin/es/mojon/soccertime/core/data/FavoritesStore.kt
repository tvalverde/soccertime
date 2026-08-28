package es.mojon.soccertime.core.data

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringSetPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import java.io.IOException

/**
 * What this device follows, kept on this device.
 *
 * The site holds a visitor's choice in a signed cookie belonging to a browser, and the API is
 * read-only with nothing a caller could present to authorise a write — so there is no server
 * side to this. That is a real consequence and not a shortcut: favourites do not follow the
 * reader from the phone to the television, and each is chosen where it is used.
 *
 * Ids rather than names, because a team can be renamed and a stored name would then follow
 * nothing. Stored as string sets because that is what `Preferences` offers; the conversion is
 * here so nothing above this ever sees a string where an id belongs.
 */
class FavoritesStore(private val store: DataStore<Preferences>) {

    /**
     * A read failure yields an empty selection rather than an exception. Losing the file is a
     * first-run screen asking the reader to choose again, which is recoverable; a crash on
     * launch is not.
     */
    val favorites: Flow<Favorites> =
        store.data
            .catch { cause -> if (cause is IOException) emit(EMPTY) else throw cause }
            .map { stored ->
                Favorites(
                    teamIds = stored[TEAMS].toIds(),
                    competitionIds = stored[COMPETITIONS].toIds(),
                )
            }

    suspend fun setTeam(id: Int, followed: Boolean) = update(TEAMS, id, followed)

    suspend fun setCompetition(id: Int, followed: Boolean) = update(COMPETITIONS, id, followed)

    suspend fun clear() {
        store.edit { it.remove(TEAMS); it.remove(COMPETITIONS) }
    }

    private suspend fun update(key: Preferences.Key<Set<String>>, id: Int, followed: Boolean) {
        store.edit { stored ->
            val current = stored[key].orEmpty()
            stored[key] = if (followed) current + id.toString() else current - id.toString()
        }
    }

    /** A value that is not an id is dropped, not fatal: it can only come from a corrupt file. */
    private fun Set<String>?.toIds(): Set<Int> = orEmpty().mapNotNull(String::toIntOrNull).toSet()

    companion object {
        const val FILE_NAME: String = "favorites"

        private val TEAMS = stringSetPreferencesKey("team_ids")
        private val COMPETITIONS = stringSetPreferencesKey("competition_ids")
        private val EMPTY = androidx.datastore.preferences.core.emptyPreferences()
    }
}
