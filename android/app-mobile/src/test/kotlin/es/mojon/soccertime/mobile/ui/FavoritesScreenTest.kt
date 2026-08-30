package es.mojon.soccertime.mobile.ui

import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import es.mojon.soccertime.core.data.FollowedItem
import es.mojon.soccertime.core.data.Following
import es.mojon.soccertime.core.data.FontScale
import es.mojon.soccertime.core.ui.FavoritesUiState
import es.mojon.soccertime.mobile.ui.theme.SoccertimeTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * The first screen this harness ever checks. Until it existed, every presentation change was
 * verified by eye on a device — a full session of UI work was spent that way — so what these
 * assert is deliberately what the reader sees: the real strings, from the real resources.
 */
@RunWith(RobolectricTestRunner::class)
class FavoritesScreenTest {

    @get:Rule
    val compose = createComposeRule()

    private fun screen(
        state: FavoritesUiState = FavoritesUiState(),
        following: Following = Following(),
        onEdit: () -> Unit = {},
        onFontScale: (FontScale) -> Unit = {},
    ) {
        compose.setContent {
            SoccertimeTheme {
                FavoritesScreen(
                    state = state,
                    following = following,
                    fontScale = FontScale.MEDIUM,
                    onIntent = {},
                    onFontScale = onFontScale,
                    onEdit = onEdit,
                    onBrowseAgenda = {},
                    onOpen = {},
                    onNarrow = {},
                )
            }
        }
    }

    /** A screen past the first run, with one followed team on the strip. */
    private fun followingOne() = Following(teams = listOf(FollowedItem(1, "FC Barcelona", null)))

    @Test
    fun `a fresh install is invited to choose, and the button leads to the editor`() {
        var edits = 0
        screen(onEdit = { edits++ })

        compose.onNodeWithText("Elige tus favoritos").assertIsDisplayed()
        compose.onNodeWithText("Elegir equipos y competiciones").performClick()
        assertEquals(1, edits)
    }

    /**
     * The Editar pill went because it duplicated the (+) tile at the end of the strip. The
     * one "Editar" left is that tile's caption; a second one is the pill coming back.
     */
    @Test
    fun `the header offers text sizes where the redundant Editar button used to be`() {
        screen(state = FavoritesUiState(chosenNothing = false), following = followingOne())

        compose.onNodeWithContentDescription("Tamaño del texto").assertIsDisplayed()
        compose.onAllNodesWithText("Editar").assertCountEquals(1)
    }

    @Test
    fun `choosing Grande reports the large scale`() {
        var chosen: FontScale? = null
        screen(
            state = FavoritesUiState(chosenNothing = false),
            following = followingOne(),
            onFontScale = { chosen = it },
        )

        compose.onNodeWithContentDescription("Tamaño del texto").performClick()
        compose.onNodeWithContentDescription("Grande").performClick()

        assertEquals(FontScale.LARGE, chosen)
    }

    @Test
    fun `loading is unmissable, not one muted line`() {
        screen(
            state = FavoritesUiState(chosenNothing = false, loading = true),
            following = followingOne(),
        )

        compose.onNodeWithText("Cargando…").assertIsDisplayed()
        compose.onNodeWithText("Buscando los próximos eventos").assertIsDisplayed()
    }
}
