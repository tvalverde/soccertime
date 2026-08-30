package es.mojon.soccertime.tv.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import es.mojon.soccertime.core.ui.ChannelChip
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.core.ui.Side
import es.mojon.soccertime.tv.ui.theme.SoccertimeTvTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** The television's first harness test: a row says who plays, where, and at what time. */
@RunWith(RobolectricTestRunner::class)
class TvEventRowTest {

    @get:Rule
    val compose = createComposeRule()

    @Test
    fun `a match row names both sides, the competition and the channel`() {
        compose.setContent {
            SoccertimeTvTheme {
                TvEventRow(
                    event = EventUi(
                        id = 1,
                        time = "16:15",
                        live = false,
                        favorite = true,
                        competition = "La Liga EA Sports",
                        sport = "Fútbol",
                        flagUrl = null,
                        title = null,
                        details = null,
                        home = Side("FC Barcelona", null),
                        away = Side("Valencia CF", null),
                        channels = listOf(ChannelChip("DAZN LaLiga", openable = true)),
                        hiddenChannels = 0,
                        openable = true,
                    ),
                    onOpen = {},
                    onFollow = {},
                )
            }
        }

        compose.onNodeWithText("FC Barcelona").assertIsDisplayed()
        compose.onNodeWithText("Valencia CF").assertIsDisplayed()
        compose.onNodeWithText("La Liga EA Sports", substring = true).assertIsDisplayed()
        compose.onNodeWithText("16:15").assertIsDisplayed()
    }
}
