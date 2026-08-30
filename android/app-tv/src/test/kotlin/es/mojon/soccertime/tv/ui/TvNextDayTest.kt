package es.mojon.soccertime.tv.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import es.mojon.soccertime.core.ui.AgendaDay
import es.mojon.soccertime.core.ui.AgendaUiState
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.tv.ui.theme.SoccertimeTvTheme
import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** The remote's way past the end of the listing: more of today, then the day after. */
@RunWith(RobolectricTestRunner::class)
class TvNextDayTest {

    @get:Rule
    val compose = createComposeRule()

    private var more = 0
    private var nextDays = 0

    private fun screen(state: AgendaUiState) {
        compose.setContent {
            SoccertimeTvTheme {
                TvAgendaScreen(
                    state = state,
                    covered = false,
                    onOpen = {},
                    onFollow = {},
                    onLoadMore = { more++ },
                    onLoadNextDay = { nextDays++ },
                )
            }
        }
    }

    private fun oneDay() = listOf(
        AgendaDay(
            date = LocalDate.of(2026, 8, 30),
            label = "HOY · DOM 30 AGO",
            events = listOf(
                EventUi(
                    id = 1,
                    time = "18:00",
                    live = false,
                    favorite = false,
                    competition = "La Liga EA Sports",
                    sport = "Fútbol",
                    flagUrl = null,
                    title = "Jornada 3",
                    details = null,
                    home = null,
                    away = null,
                    channels = emptyList(),
                    hiddenChannels = 0,
                    openable = false,
                ),
            ),
        ),
    )

    @Test
    fun `an exhausted day ends on a row that loads tomorrow`() {
        screen(
            AgendaUiState(
                day = LocalDate.of(2026, 8, 30),
                days = oneDay(),
                nextDayLabel = "MAÑANA · LUN 31 AGO",
                canLoadMore = false,
            ),
        )

        compose.onNodeWithText("Cargar MAÑANA · LUN 31 AGO").performClick()
        assertEquals(1, nextDays)
        assertEquals(0, more)
    }

    @Test
    fun `while pages of today remain, the row says Ver más instead`() {
        screen(
            AgendaUiState(
                day = LocalDate.of(2026, 8, 30),
                days = oneDay(),
                nextDayLabel = "MAÑANA · LUN 31 AGO",
                canLoadMore = true,
            ),
        )

        compose.onNodeWithText("Ver más").assertIsDisplayed()
        compose.onNodeWithText("Ver más").performClick()
        assertEquals(1, more)
        assertEquals(0, nextDays)
    }
}
