package es.mojon.soccertime.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import es.mojon.soccertime.core.data.FollowedItem
import es.mojon.soccertime.core.data.Following
import es.mojon.soccertime.core.ui.FollowableKind
import es.mojon.soccertime.core.ui.FollowableUi
import es.mojon.soccertime.core.ui.ManageIntent
import es.mojon.soccertime.core.ui.ManageUiState
import es.mojon.soccertime.mobile.ui.theme.SoccertimeTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** The screen that answers "what do I follow?" without being asked to search first. */
@RunWith(RobolectricTestRunner::class)
class ManageFavoritesScreenTest {

    @get:Rule
    val compose = createComposeRule()

    private val racing = FollowedItem(7, "Racing de Santander")
    private val alcorcon = FollowedItem(21, "AD Alcorcón")

    private val intents = mutableListOf<ManageIntent>()
    private var exports = 0
    private var imports = 0

    private fun screen(state: ManageUiState) {
        compose.setContent {
            SoccertimeTheme {
                ManageFavoritesScreen(
                    state = state,
                    onIntent = { intents += it },
                    onBack = {},
                    onExport = { exports++ },
                    onImport = { imports++ },
                )
            }
        }
    }

    @Test
    fun `what is followed opens the screen, and its star unfollows without a search`() {
        screen(
            ManageUiState(
                following = Following(teams = listOf(racing)),
                results = listOf(FollowableUi(alcorcon, followed = false, kind = FollowableKind.Teams)),
                total = 4796,
            ),
        )

        compose.onNodeWithText("SIGUIENDO").assertIsDisplayed()
        compose.onNodeWithText("Racing de Santander").performClick()

        assertEquals(
            listOf<ManageIntent>(ManageIntent.Follow(racing, false, FollowableKind.Teams)),
            intents,
        )
    }

    @Test
    fun `searching asks a different question, so the followed section steps aside`() {
        screen(
            ManageUiState(
                query = "alco",
                following = Following(teams = listOf(racing)),
                results = listOf(FollowableUi(alcorcon, followed = false, kind = FollowableKind.Teams)),
                total = 1,
            ),
        )

        compose.onNodeWithText("SIGUIENDO").assertDoesNotExist()
        compose.onNodeWithText("AD Alcorcón").assertIsDisplayed()
    }

    @Test
    fun `export and import are always at hand`() {
        screen(ManageUiState(following = Following(teams = listOf(racing))))

        compose.onNodeWithText("Exportar").performClick()
        compose.onNodeWithText("Importar").performClick()

        assertEquals(1, exports)
        assertEquals(1, imports)
        assertTrue(intents.isEmpty())
    }
}
