package es.mojon.soccertime.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipe
import androidx.compose.ui.test.swipeUp
import es.mojon.soccertime.core.network.ApiError
import es.mojon.soccertime.core.ui.AgendaDay
import es.mojon.soccertime.core.ui.AgendaFilter
import es.mojon.soccertime.core.ui.AgendaIntent
import es.mojon.soccertime.core.ui.AgendaUiState
import es.mojon.soccertime.core.ui.FollowableKind
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.mobile.ui.theme.SoccertimeTheme
import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** The chip that used to be a bare label now opens the calendar, and wears the chosen day. */
@RunWith(RobolectricTestRunner::class)
class AgendaScreenTest {

    @get:Rule
    val compose = createComposeRule()

    private val august30: LocalDate = LocalDate.of(2026, 8, 30)

    private val intents = mutableListOf<AgendaIntent>()

    private fun screen(state: AgendaUiState) {
        compose.setContent {
            SoccertimeTheme {
                AgendaScreen(
                    state = state,
                    onIntent = { intents += it },
                    onOpen = {},
                    dayLabel = { "sáb 5 sep" },
                )
            }
        }
    }

    @Test
    fun `pressing the window chip peeks the month and opens the calendar`() {
        screen(AgendaUiState(day = august30))

        compose.onNodeWithText("Ayer y hoy").performClick()

        compose.onNodeWithText("Ver este día").assertIsDisplayed()
        compose.onNodeWithText("Cancelar").assertIsDisplayed()
        // Asked before the dialog exists, so the index usually beats the grid.
        assertTrue(intents.contains(AgendaIntent.PeekMonth(java.time.YearMonth.of(2026, 8))))
    }

    @Test
    fun `a chosen day is worn by the chip and its cross takes it off`() {
        screen(AgendaUiState(day = LocalDate.of(2026, 9, 5), chosenDay = LocalDate.of(2026, 9, 5)))

        compose.onNodeWithText("sáb 5 sep").assertIsDisplayed()
        compose.onNodeWithContentDescription("Volver a ayer y hoy").performClick()

        assertEquals(listOf<AgendaIntent>(AgendaIntent.PickDay(null)), intents)
    }

    private fun oneQuietDay() = listOf(
        AgendaDay(
            date = august30,
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
                    title = null,
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
    fun `an exhausted day ends on the foot that loads tomorrow, and pressing it asks for it`() {
        screen(
            AgendaUiState(
                day = august30,
                days = oneQuietDay(),
                nextDayLabel = "MAÑANA · LUN 31 AGO",
                canLoadMore = false,
            ),
        )

        compose.onNodeWithText("MAÑANA · LUN 31 AGO").performClick()

        assertEquals(listOf<AgendaIntent>(AgendaIntent.LoadNextDay), intents)
    }

    @Test
    fun `pulling past the end and releasing asks for tomorrow`() {
        screen(
            AgendaUiState(
                day = august30,
                days = oneQuietDay(),
                nextDayLabel = "MAÑANA · LUN 31 AGO",
                canLoadMore = false,
            ),
        )

        compose.onRoot().performTouchInput { swipeUp() }

        assertEquals(listOf<AgendaIntent>(AgendaIntent.LoadNextDay), intents)
    }

    @Test
    fun `releasing before the ring fills loads nothing`() {
        screen(
            AgendaUiState(
                day = august30,
                days = oneQuietDay(),
                nextDayLabel = "MAÑANA · LUN 31 AGO",
                canLoadMore = false,
            ),
        )

        // A 40-pixel pull against a 112-pixel threshold: felt, shown, and let go of.
        compose.onRoot().performTouchInput {
            swipe(start = center, end = center.copy(y = center.y - 40f), durationMillis = 300)
        }

        assertEquals(emptyList<AgendaIntent>(), intents)
    }

    @Test
    fun `while pages of today remain, the foot is withheld and the next page asks for itself`() {
        screen(
            AgendaUiState(
                day = august30,
                days = oneQuietDay(),
                nextDayLabel = "MAÑANA · LUN 31 AGO",
                canLoadMore = true,
            ),
        )

        compose.onNodeWithText("MAÑANA · LUN 31 AGO").assertDoesNotExist()
        // The button is gone; being near the end of what is loaded is the ask now.
        compose.onNodeWithText("Ver más").assertDoesNotExist()
        assertEquals(listOf<AgendaIntent>(AgendaIntent.LoadMore), intents)
    }

    @Test
    fun `a page on its way is a quiet row, and a failed one pauses the automatic ask`() {
        screen(
            AgendaUiState(
                day = august30,
                days = oneQuietDay(),
                canLoadMore = true,
                loading = true,
                error = ApiError.Offline,
            ),
        )

        compose.onNodeWithText("Cargando más eventos…").assertIsDisplayed()
        assertEquals("the banner's Retry is the way back", emptyList<AgendaIntent>(), intents)
    }

    @Test
    fun `an empty chosen day still leads to the next one`() {
        screen(
            AgendaUiState(
                day = LocalDate.of(2026, 9, 5),
                chosenDay = LocalDate.of(2026, 9, 5),
                nextDayLabel = "DOMINGO 6 SEPTIEMBRE",
                days = emptyList(),
            ),
        )

        compose.onNodeWithText("No hay eventos para este día.").assertIsDisplayed()
        compose.onNodeWithText("DOMINGO 6 SEPTIEMBRE").performClick()

        assertEquals(listOf<AgendaIntent>(AgendaIntent.LoadNextDay), intents)
    }

    @Test
    fun `narrowed, the listing simply continues - no foot, and the chip reads Desde hoy`() {
        screen(
            AgendaUiState(
                day = august30,
                filter = AgendaFilter(42, "FC Barcelona", null, FollowableKind.Teams),
                days = oneQuietDay(),
                nextDayLabel = null,
                canLoadMore = false,
            ),
        )

        compose.onNodeWithText("FC Barcelona").assertIsDisplayed()
        compose.onNodeWithText("Desde hoy").assertIsDisplayed()
        compose.onNodeWithText("Estira hacia arriba para cargarlo").assertDoesNotExist()
    }

    @Test
    fun `narrowed with a chosen day, the chip wears where the listing starts`() {
        screen(
            AgendaUiState(
                day = LocalDate.of(2026, 9, 5),
                filter = AgendaFilter(42, "FC Barcelona", null, FollowableKind.Teams),
                chosenDay = LocalDate.of(2026, 9, 5),
                days = oneQuietDay(),
            ),
        )

        compose.onNodeWithText("sáb 5 sep").assertIsDisplayed()
    }

    @Test
    fun `loading is unmissable here too`() {
        screen(AgendaUiState(day = august30, loading = true))

        compose.onNodeWithText("Cargando…").assertIsDisplayed()
        compose.onNodeWithText("Buscando los próximos eventos").assertIsDisplayed()
    }
}
