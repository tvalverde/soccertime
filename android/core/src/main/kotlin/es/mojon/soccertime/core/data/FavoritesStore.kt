package es.mojon.soccertime.core.data

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import java.io.IOException
import kotlinx.coroutines.flow.Flow
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.retryWhen
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * What this device follows, kept on this device.
 *
 * The site holds a visitor's choice in a signed cookie belonging to a browser, and the API is
 * read-only with nothing a caller could present to authorise a write — so there is no server
 * side to this. That is a real consequence and not a shortcut: favourites do not follow the
 * reader from the phone to the television, and each is chosen where it is used.
 *
 * **The name and the crest are stored beside the id, and that is deliberate denormalisation.**
 * The landing screen opens on a row of what you follow, and resolving five ids through the
 * API would be five requests before the first frame — on a limit of thirty a minute, to draw
 * a strip. Stored this way it draws instantly, and it draws before the device has ever been
 * online. The cost is that a team renamed on the server keeps its old name here until it is
 * followed again, which is a stale label rather than a broken screen.
 *
 * The id remains what everything is decided by, so a rename changes nothing about which
 * events are covered.
 */
class FavoritesStore(private val store: DataStore<Preferences>) {

    /**
     * A read failure yields an empty selection rather than an exception. Losing the file is a
     * first-run screen asking the reader to choose again, which is recoverable; a crash on
     * launch is not.
     *
     * **And then it looks again.** `catch` would *complete* the flow after emitting, so a
     * single `IOException` ended this collector for the life of the process: the screen kept
     * the favourites it happened to hold and stopped reacting to every change after. `retryWhen`
     * re-subscribes instead, so a busy disk costs one empty reading and nothing more.
     *
     * The retries do not give up, because giving up is the bug being fixed, and they back off
     * to half a minute because four collectors share this flow and a television is left running
     * for days. `distinctUntilChanged` is what makes emitting on every failure harmless: a
     * broken streak collapses into one value, and an unchanged selection stops re-triggering
     * the agenda's redraw.
     */
    val following: Flow<Following> =
        store.data
            .retryWhen { cause, attempt ->
                if (cause !is IOException) return@retryWhen false
                emit(EMPTY)
                delay(backoffFor(attempt))
                true
            }
            .map { stored ->
                Following(
                    teams = stored[TEAMS].parse(),
                    competitions = stored[COMPETITIONS].parse(),
                )
            }
            .distinctUntilChanged()

    /** What the filtering uses. Ids only, because that is all a rename cannot break. */
    val favorites: Flow<Favorites> = following.map { it.selection }

    suspend fun setTeam(item: FollowedItem, followed: Boolean) = update(TEAMS, item, followed)

    suspend fun setCompetition(item: FollowedItem, followed: Boolean) =
        update(COMPETITIONS, item, followed)

    suspend fun clear() {
        store.edit { it.remove(TEAMS); it.remove(COMPETITIONS) }
    }

    /**
     * Follow everything an import carries that is not already followed.
     *
     * Adds and never removes — restoring into a fresh installation is the same either way,
     * and into a lived-in one this destroys nothing. Ids decide identity, as everywhere:
     * something already followed keeps its current entry (name included) and is only counted,
     * and a file carrying the same id twice counts once.
     */
    suspend fun followAll(imported: Following): PortSummary {
        var added = 0
        var alreadyFollowed = 0
        store.edit { stored ->
            fun merge(key: Preferences.Key<String>, items: List<FollowedItem>) {
                val current = stored[key].parse()
                val known = current.mapTo(mutableSetOf()) { it.id }
                val (old, new) = items.distinctBy { it.id }.partition { it.id in known }
                added += new.size
                alreadyFollowed += old.size
                if (new.isNotEmpty()) {
                    stored[key] = JSON.encodeToString((current + new).sortedBy { it.name.lowercase() })
                }
            }
            merge(TEAMS, imported.teams)
            merge(COMPETITIONS, imported.competitions)
        }
        return PortSummary(added, alreadyFollowed)
    }

    private suspend fun update(
        key: Preferences.Key<String>,
        item: FollowedItem,
        followed: Boolean,
    ) {
        store.edit { stored ->
            val current = stored[key].parse().filterNot { it.id == item.id }
            val next = if (followed) current + item else current
            stored[key] = JSON.encodeToString(next.sortedBy { it.name.lowercase() })
        }
    }

    /** A value that cannot be read is one nobody can have written by hand; treat it as none. */
    private fun String?.parse(): List<FollowedItem> =
        this?.let { runCatching { JSON.decodeFromString<List<FollowedItem>>(it) }.getOrNull() }
            .orEmpty()

    private fun backoffFor(attempt: Long): Duration =
        FIRST_RETRY * (1 shl attempt.coerceAtMost(RETRY_DOUBLINGS).toInt())
            .coerceAtMost(Int.MAX_VALUE)

    companion object {
        const val FILE_NAME: String = "favorites"

        private val FIRST_RETRY = 250.milliseconds
        private const val RETRY_DOUBLINGS = 7L

        private val TEAMS = stringPreferencesKey("teams")
        private val COMPETITIONS = stringPreferencesKey("competitions")
        private val EMPTY = androidx.datastore.preferences.core.emptyPreferences()
        private val JSON = Json { ignoreUnknownKeys = true }
    }
}

/** What an import did: what it added, and what was already there. */
data class PortSummary(val added: Int, val alreadyFollowed: Int) {
    val total: Int get() = added + alreadyFollowed
}

/** A team or a competition the reader chose, with just enough to draw it. */
@Serializable
data class FollowedItem(
    val id: Int,
    val name: String,
    val imageUrl: String? = null,
)

data class Following(
    val teams: List<FollowedItem> = emptyList(),
    val competitions: List<FollowedItem> = emptyList(),
) {
    val isEmpty: Boolean get() = teams.isEmpty() && competitions.isEmpty()

    /** The ids, which is what decides whether an event is covered. */
    val selection: Favorites
        get() = Favorites(
            teamIds = teams.mapTo(mutableSetOf(), FollowedItem::id),
            competitionIds = competitions.mapTo(mutableSetOf(), FollowedItem::id),
        )
}
