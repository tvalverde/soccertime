package es.mojon.soccertime.mobile.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeLeft
import androidx.compose.ui.test.swipeRight
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** The gesture the sections are reached by: a horizontal swipe, in both directions. */
@RunWith(RobolectricTestRunner::class)
class HomePagerTest {

    @get:Rule
    val compose = createComposeRule()

    private fun pager() {
        compose.setContent {
            HomePager(
                state = rememberPagerState(initialPage = FAVORITES_PAGE) { SECTION_COUNT },
                modifier = Modifier.fillMaxSize(),
                favorites = { Text("favoritos aquí") },
                agenda = { Text("agenda aquí") },
            )
        }
    }

    @Test
    fun `swiping left reaches the agenda, and swiping right comes back`() {
        pager()
        compose.onNodeWithText("favoritos aquí").assertIsDisplayed()

        compose.onRoot().performTouchInput { swipeLeft() }
        compose.onNodeWithText("agenda aquí").assertIsDisplayed()

        compose.onRoot().performTouchInput { swipeRight() }
        compose.onNodeWithText("favoritos aquí").assertIsDisplayed()
    }
}
