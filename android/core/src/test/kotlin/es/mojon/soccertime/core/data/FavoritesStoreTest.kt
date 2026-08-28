package es.mojon.soccertime.core.data

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import java.io.File
import java.io.IOException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emitAll
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.job
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * The store keeps what was chosen, across a restart.
 *
 * Run on the JVM against a real file rather than a fake, because the part worth testing is
 * exactly the part a fake would skip: that a set written now is the set read back by a
 * process that starts later, which is what a favourite surviving the app being closed means.
 *
 * Reopening is modelled by cancelling the scope the store was built with and building another,
 * because that is the only way there is: `DataStore` has no `close`, and it refuses outright
 * to have two instances alive on one file. That refusal is also a constraint on the
 * application — `AppGraph` holds exactly one `FavoritesStore`, and a second one built
 * anywhere would throw on first use rather than quietly disagree.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class FavoritesStoreTest {

    @get:Rule
    val folder = TemporaryFolder()

    private val open = mutableListOf<CoroutineScope>()

    @After
    fun closeEverything() = open.forEach { it.cancel() }

    private val file: File get() = folder.root.resolve("favorites.preferences_pb")

    private fun openStore(): FavoritesStore {
        val scope = CoroutineScope(UnconfinedTestDispatcher() + Job())
        open += scope
        return FavoritesStore(PreferenceDataStoreFactory.create(scope = scope) { file })
    }

    /**
     * What closing the application does. Joining is not tidiness: DataStore releases its
     * claim on the file when the coordinating job *completes*, not when it is cancelled, and
     * reopening before that fails with the same "multiple DataStores active" that a second
     * store built in a running app would.
     */
    private suspend fun closeStore() {
        open.forEach { it.coroutineContext.job.cancelAndJoin() }
        open.clear()
    }

    private val athletic = FollowedItem(322, "Athletic Club", "https://www.mojon.es/…/athletic.webp")
    private val madrid = FollowedItem(1, "Real Madrid", "https://www.mojon.es/…/madrid.webp")
    private val laLiga = FollowedItem(10, "La Liga EA Sports", null)

    /**
     * Reading fails once and then works, which is what a busy disk looks like.
     *
     * Wrapping rather than building a second `DataStore`: two instances on one file is what
     * the real thing refuses outright, and the interface is only these two members.
     */
    private class FailsOnce(private val real: DataStore<Preferences>) : DataStore<Preferences> {
        private var thrown = false

        override val data: Flow<Preferences> = flow {
            if (!thrown) {
                thrown = true
                throw IOException("the disk was busy")
            }
            emitAll(real.data)
        }

        override suspend fun updateData(
            transform: suspend (Preferences) -> Preferences,
        ): Preferences = real.updateData(transform)
    }

    /**
     * `Flow.catch` *completes* the flow after emitting, so one failed read ended this
     * collector for the life of the process: the screen kept the favourites it had and stopped
     * reacting to every change afterwards.
     */
    @Test
    fun `a read that fails once is read again, rather than never`() = runTest {
        // Seeded first, and this matters: with an empty store the value recovered would equal
        // the empty one emitted on failure, and `distinctUntilChanged` would collapse the two
        // into a single emission — the test would pass while proving nothing.
        val scope = CoroutineScope(UnconfinedTestDispatcher() + Job())
        open += scope
        val real = PreferenceDataStoreFactory.create(scope = scope) { file }
        FavoritesStore(real).setTeam(athletic, followed = true)

        val seen = FavoritesStore(FailsOnce(real)).following.take(2).toList()

        assertTrue("a failed read is an empty selection, not a crash", seen.first().isEmpty)
        assertEquals("and then the real one arrives", listOf(athletic), seen[1].teams)
    }

    @Test
    fun `a device that has chosen nothing follows nothing`() = runTest {
        val store = openStore()

        assertTrue(store.following.first().isEmpty)
        assertEquals(Favorites.NONE, store.favorites.first())
    }

    @Test
    fun `what was followed is read back, name and crest included`() = runTest {
        val store = openStore()

        store.setTeam(athletic, followed = true)
        store.setCompetition(laLiga, followed = true)

        val kept = store.following.first()
        assertEquals(listOf(athletic), kept.teams)
        assertEquals(listOf(laLiga), kept.competitions)
        assertEquals(Favorites(teamIds = setOf(322), competitionIds = setOf(10)), kept.selection)
    }

    @Test
    fun `it survives the app being closed and opened again`() = runTest {
        openStore().apply {
            setTeam(athletic, followed = true)
            setTeam(madrid, followed = true)
            setCompetition(laLiga, followed = true)
        }

        closeStore()
        val afterRestart = openStore().following.first()

        assertEquals(setOf(322, 1), afterRestart.selection.teamIds)
        assertEquals("the strip can be drawn before the device is online", "Athletic Club",
            afterRestart.teams.first { it.id == 322 }.name)
        assertEquals(setOf(10), afterRestart.selection.competitionIds)
    }

    @Test
    fun `the strip comes back in a stable order rather than a random one`() = runTest {
        val store = openStore()

        store.setTeam(madrid, followed = true)
        store.setTeam(athletic, followed = true)

        assertEquals(listOf("Athletic Club", "Real Madrid"), store.following.first().teams.map { it.name })
    }

    @Test
    fun `following the same team twice keeps one of it`() = runTest {
        val store = openStore()

        store.setTeam(athletic, followed = true)
        store.setTeam(athletic.copy(name = "Athletic Club (renamed)"), followed = true)

        val teams = store.following.first().teams
        assertEquals(1, teams.size)
        assertEquals("the newer name wins", "Athletic Club (renamed)", teams.single().name)
    }

    @Test
    fun `unfollowing removes only that one`() = runTest {
        val store = openStore()
        store.setTeam(athletic, followed = true)
        store.setTeam(madrid, followed = true)

        store.setTeam(athletic, followed = false)

        assertEquals(listOf(madrid), store.following.first().teams)
    }

    @Test
    fun `teams and competitions do not overwrite each other`() = runTest {
        val store = openStore()
        val sameId = FollowedItem(7, "seven")
        store.setTeam(sameId, followed = true)
        store.setCompetition(sameId, followed = true)

        store.setTeam(sameId, followed = false)

        val kept = store.following.first()
        assertTrue(kept.teams.isEmpty())
        assertEquals(listOf(sameId), kept.competitions)
    }

    @Test
    fun `clearing leaves the first-run state, not a broken one`() = runTest {
        val store = openStore()
        store.setTeam(athletic, followed = true)
        store.setCompetition(laLiga, followed = true)

        store.clear()

        assertTrue(store.following.first().isEmpty)
        assertEquals(Favorites.NONE, store.favorites.first())
    }
}
