package es.mojon.soccertime.core.data

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
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

    @Test
    fun `a device that has chosen nothing follows nothing`() = runTest {
        val store = openStore()

        assertEquals(Favorites.NONE, store.favorites.first())
        assertTrue(store.favorites.first().isEmpty)
    }

    @Test
    fun `what was followed is read back`() = runTest {
        val store = openStore()

        store.setTeam(id = 322, followed = true)
        store.setCompetition(id = 10, followed = true)

        assertEquals(
            Favorites(teamIds = setOf(322), competitionIds = setOf(10)),
            store.favorites.first(),
        )
    }

    @Test
    fun `it survives the app being closed and opened again`() = runTest {
        openStore().apply {
            setTeam(id = 322, followed = true)
            setTeam(id = 1, followed = true)
            setCompetition(id = 10, followed = true)
        }

        closeStore()
        val afterRestart = openStore().favorites.first()

        assertEquals(setOf(322, 1), afterRestart.teamIds)
        assertEquals(setOf(10), afterRestart.competitionIds)
    }

    @Test
    fun `unfollowing removes only that one`() = runTest {
        val store = openStore()
        store.setTeam(id = 322, followed = true)
        store.setTeam(id = 1, followed = true)

        store.setTeam(id = 322, followed = false)

        assertEquals(setOf(1), store.favorites.first().teamIds)
    }

    @Test
    fun `teams and competitions do not overwrite each other`() = runTest {
        val store = openStore()
        store.setTeam(id = 7, followed = true)
        store.setCompetition(id = 7, followed = true)

        store.setTeam(id = 7, followed = false)

        val kept = store.favorites.first()
        assertEquals(emptySet<Int>(), kept.teamIds)
        assertEquals(setOf(7), kept.competitionIds)
    }

    @Test
    fun `clearing leaves the first-run state, not a broken one`() = runTest {
        val store = openStore()
        store.setTeam(id = 322, followed = true)
        store.setCompetition(id = 10, followed = true)

        store.clear()

        assertEquals(Favorites.NONE, store.favorites.first())
    }
}
