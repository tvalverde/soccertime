package es.mojon.soccertime.core.data

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * On the JVM against a real file, for the same reason `FavoritesStoreTest` is: what matters
 * is that the size chosen now is the size read back by a process that starts later.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class SettingsStoreTest {

    @get:Rule
    val folder = TemporaryFolder()

    private val open = mutableListOf<CoroutineScope>()

    @After
    fun closeEverything() = open.forEach { it.cancel() }

    private val file: File get() = folder.root.resolve("settings.preferences_pb")

    private fun scope(): CoroutineScope = CoroutineScope(UnconfinedTestDispatcher() + Job()).also { open += it }

    private fun openStore(): SettingsStore =
        SettingsStore(PreferenceDataStoreFactory.create(scope = scope()) { file })

    @Test
    fun `the default is the size every screen was designed at`() = runTest {
        assertEquals(FontScale.MEDIUM, openStore().fontScale.first())
    }

    @Test
    fun `a chosen size survives a restart`() = runTest {
        openStore().setFontScale(FontScale.LARGE)
        open.removeLast().cancel()

        assertEquals(FontScale.LARGE, openStore().fontScale.first())
    }

    @Test
    fun `a value written by a future version reads as the default, not a crash`() = runTest {
        val raw = PreferenceDataStoreFactory.create(scope = scope()) { file }
        raw.edit { it[stringPreferencesKey("font_scale")] = "ENORMOUS" }
        open.removeLast().cancel()

        assertEquals(FontScale.MEDIUM, openStore().fontScale.first())
    }
}
