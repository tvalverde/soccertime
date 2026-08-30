package es.mojon.soccertime.mobile.ui

import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.PagerState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/** The sections a horizontal swipe moves between, in the order the bottom bar draws them. */
const val FAVORITES_PAGE = 0
const val AGENDA_PAGE = 1
const val SECTION_COUNT = 2

/**
 * Favourites and the agenda side by side, reached by swiping as well as by the bar.
 *
 * A pager instead of two navigation destinations, because the two are peers the reader moves
 * between constantly and navigation treats every move as a journey. The page contents stay
 * lambdas so this stays wiring: what each section is remains the caller's statement, and a
 * future section is one more page here and one more item on the bar.
 */
@Composable
fun HomePager(
    state: PagerState,
    modifier: Modifier = Modifier,
    favorites: @Composable () -> Unit,
    agenda: @Composable () -> Unit,
) {
    HorizontalPager(state = state, modifier = modifier) { page ->
        when (page) {
            FAVORITES_PAGE -> favorites()
            else -> agenda()
        }
    }
}
