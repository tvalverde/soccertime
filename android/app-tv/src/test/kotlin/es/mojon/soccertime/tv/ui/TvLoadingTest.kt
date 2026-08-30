package es.mojon.soccertime.tv.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import es.mojon.soccertime.core.ui.AgendaUiState
import es.mojon.soccertime.tv.ui.theme.SoccertimeTvTheme
import java.time.LocalDate
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** From three metres a muted line is invisible; loading has to say so out loud. */
@RunWith(RobolectricTestRunner::class)
class TvLoadingTest {

    @get:Rule
    val compose = createComposeRule()

    @Test
    fun `a loading agenda is unmissable, not one muted line`() {
        compose.setContent {
            SoccertimeTvTheme {
                TvAgendaScreen(
                    state = AgendaUiState(day = LocalDate.of(2026, 8, 30), loading = true),
                    covered = false,
                    onOpen = {},
                    onFollow = {},
                    onLoadMore = {},
                    onLoadNextDay = {},
                )
            }
        }

        compose.onNodeWithText("Cargando…").assertIsDisplayed()
        compose.onNodeWithText("Buscando los próximos eventos").assertIsDisplayed()
    }
}
