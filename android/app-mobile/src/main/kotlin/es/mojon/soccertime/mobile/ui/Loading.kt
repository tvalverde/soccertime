package es.mojon.soccertime.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.mobile.R

/**
 * The first answer takes seconds, and what fills them has to be unmissable.
 *
 * This used to be one 13.5sp line of muted text — the same voice as an empty state — so a
 * screen that was busy answering read exactly like a screen with nothing to say. A ring in
 * the palette's loudest green plus a display-face title is the opposite claim: something is
 * happening, and the rows are on their way.
 *
 * Every listing shares this one composable, so favourites, the agenda and whatever section
 * comes next cannot each drift into their own idea of "loading".
 */
@Composable
fun LoadingState(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator(
            color = MaterialTheme.colorScheme.primary,
            trackColor = Color(Palette.HAIRLINE),
            strokeWidth = 4.dp,
            modifier = Modifier.size(56.dp),
        )
        Text(
            text = stringResource(R.string.loading),
            style = MaterialTheme.typography.headlineSmall,
            fontSize = 19.sp,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.padding(top = 18.dp),
        )
        Text(
            text = stringResource(R.string.loading_body),
            fontSize = 13.sp,
            color = Color(Palette.ON_BACKGROUND_MUTED),
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}
