package es.mojon.soccertime.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import es.mojon.soccertime.core.network.ApiError
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.mobile.R

/**
 * A failure in the reader's terms.
 *
 * `RateLimited` reads the seconds off the header when the server sent one, because "try again
 * in twelve seconds" is actionable where "too many requests" is not — and the two refusals in
 * front of this API disagree about their body, so the header is the only thing that reliably
 * carries it.
 */
@Composable
fun describe(error: ApiError): String = when (error) {
    is ApiError.Offline -> stringResource(R.string.error_offline)
    is ApiError.RateLimited -> error.retryAfterSeconds
        ?.let { pluralStringResource(R.plurals.error_rate_limited_wait, it.toInt(), it) }
        ?: stringResource(R.string.error_rate_limited)
    is ApiError.BadRequest -> error.message
    is ApiError.Http -> stringResource(R.string.error_http, error.code)
    is ApiError.Unexpected -> stringResource(R.string.error_unexpected)
}

/**
 * Shown over rows that are still there. The banner says the answer is old rather than the
 * screen saying nothing: an agenda a minute out of date beats no agenda on a screen opened to
 * find out what is on right now.
 */
@Composable
fun FailureBanner(
    error: ApiError,
    showingStale: Boolean,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .padding(start = 12.dp, top = 8.dp, end = 4.dp, bottom = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = SoccertimeIcons.Warning,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.error,
            modifier = Modifier.size(16.dp),
        )
        Text(
            text = if (showingStale) {
                "${describe(error)} ${stringResource(R.string.showing_stale)}"
            } else {
                describe(error)
            },
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 12.sp,
            modifier = Modifier.weight(1f),
        )
        IconButton(onClick = onRetry) {
            Icon(
                imageVector = SoccertimeIcons.Refresh,
                contentDescription = stringResource(R.string.refresh),
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(18.dp),
            )
        }
    }
}

@Composable
fun EmptyState(message: String, modifier: Modifier = Modifier) {
    Text(
        text = message,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        fontSize = 13.5.sp,
        modifier = modifier.fillMaxWidth().padding(vertical = 28.dp, horizontal = 8.dp),
    )
}
