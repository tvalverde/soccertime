package es.mojon.soccertime.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.Icon
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import es.mojon.soccertime.core.data.FollowedItem
import es.mojon.soccertime.core.data.Following
import es.mojon.soccertime.core.network.ApiError
import es.mojon.soccertime.core.ui.AgendaDay
import es.mojon.soccertime.core.ui.AgendaUiState
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.core.ui.FavoritesUiState
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.tv.R
import es.mojon.soccertime.tv.ui.theme.TvHeading
import es.mojon.soccertime.tv.ui.theme.TvLabel
import es.mojon.soccertime.tv.ui.theme.TvMeta
import es.mojon.soccertime.tv.ui.theme.TvScreenTitle

@Composable
fun TvFavoritesScreen(
    state: FavoritesUiState,
    following: Following,
    clockLabel: String,
    onOpen: (EventUi) -> Unit,
    onFollow: (EventUi) -> Unit,
    modifier: Modifier = Modifier,
) {
    val firstRow = remember { FocusRequester() }

    // Somebody has to hold the focus or the first press of the D-pad goes nowhere. Guarded,
    // because the requester is only attached once the row exists and asking before that throws.
    LaunchedEffect(state.days.firstOrNull()?.date) {
        if (state.days.isNotEmpty()) runCatching { firstRow.requestFocus() }
    }

    Column(modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                text = stringResource(R.string.favorites_title),
                style = TvScreenTitle,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Box(Modifier.weight(1f))
            Text(text = clockLabel, style = TvMeta, color = Color(Palette.ON_BACKGROUND_FAINT))
        }

        if (state.chosenNothing) {
            TvFirstRun()
            return@Column
        }

        FollowedStrip(following)

        state.error?.let { TvFailure(it, state.showingStale) }

        // The first answer takes seconds, and a blank screen for seconds is indistinguishable
        // from a broken app. Only while there is nothing yet: a refresh over rows already on
        // screen must not blank them.
        if (state.loading && state.days.isEmpty()) {
            Text(
                text = stringResource(R.string.loading),
                style = TvLabel,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 20.dp),
            )
            return@Column
        }

        if (state.nothingComingUp) {
            Text(
                text = stringResource(R.string.nothing_coming_up),
                style = TvLabel,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 20.dp),
            )
            return@Column
        }

        TvEventList(state.days, firstRow, onOpen, onFollow)
    }
}

@Composable
fun TvAgendaScreen(
    state: AgendaUiState,
    onOpen: (EventUi) -> Unit,
    onFollow: (EventUi) -> Unit,
    modifier: Modifier = Modifier,
) {
    val firstRow = remember { FocusRequester() }

    // Somebody has to hold the focus or the first press of the D-pad goes nowhere. Guarded,
    // because the requester is only attached once the row exists and asking before that throws.
    LaunchedEffect(state.days.firstOrNull()?.date) {
        if (state.days.isNotEmpty()) runCatching { firstRow.requestFocus() }
    }

    Column(modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(13.dp)) {
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                text = stringResource(R.string.tab_agenda),
                style = TvScreenTitle,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Box(Modifier.weight(1f))
            if (state.count > 0) {
                Text(
                    text = pluralStringResource(R.plurals.event_count, state.count, state.count),
                    style = TvMeta,
                    color = Color(Palette.ON_BACKGROUND_FAINT),
                )
            }
        }

        state.error?.let { TvFailure(it, state.showingStale) }

        // The first answer takes seconds, and a blank screen for seconds is indistinguishable
        // from a broken app. Only while there is nothing yet: a refresh over rows already on
        // screen must not blank them.
        if (state.loading && state.days.isEmpty()) {
            Text(
                text = stringResource(R.string.loading),
                style = TvLabel,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 20.dp),
            )
            return@Column
        }

        if (state.isEmpty) {
            Text(
                text = stringResource(R.string.empty_agenda),
                style = TvLabel,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 20.dp),
            )
            return@Column
        }

        TvEventList(state.days, firstRow, onOpen, onFollow)
    }
}

/**
 * The list every screen here shows.
 *
 * `clipToPadding` is off and the padding is horizontal, because the focused row's halo is
 * drawn outside its own bounds: a list that clipped would cut the one thing that says where
 * the remote is.
 */
@Composable
private fun TvEventList(
    days: List<AgendaDay>,
    firstRow: FocusRequester,
    onOpen: (EventUi) -> Unit,
    onFollow: (EventUi) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
        verticalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        days.forEachIndexed { dayIndex, day ->
            item(key = "day-${day.date}") { TvDayHeading(day.label) }
            // By position, not by equality. Two events of the same day can be equal as data —
            // the same pair of players at two different times differs only by its id — and
            // comparing them by value attached one `FocusRequester` to several rows, which is
            // undefined and left the remote unable to move between them.
            itemsIndexed(day.events, key = { _, event -> event.id }) { index, event ->
                TvEventRow(
                    event = event,
                    onOpen = { onOpen(event) },
                    onFollow = { onFollow(event) },
                    focusRequester = if (dayIndex == 0 && index == 0) firstRow else null,
                )
            }
        }
    }
}

@Composable
private fun TvDayHeading(label: String) {
    Row(
        Modifier.fillMaxWidth().padding(top = 3.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text = label, style = TvHeading, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Box(Modifier.weight(1f).height(1.dp).background(Color(Palette.HAIRLINE)))
    }
}

/**
 * Drawn from the store alone. This is the first thing on the screen the app opens on, and the
 * names and crests are kept beside the ids so it needs no answer from anywhere to appear.
 */
@Composable
private fun FollowedStrip(following: Following) {
    val entries = following.teams + following.competitions
    if (entries.isEmpty()) return

    LazyRow(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
        items(entries, key = { "${it.name}-${it.id}" }) { item ->
            FollowedAvatar(item, accent = item in following.competitions)
        }
    }
}

@Composable
private fun FollowedAvatar(item: FollowedItem, accent: Boolean) {
    Column(
        Modifier.width(58.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Box(
            Modifier
                .size(48.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surface)
                .border(
                    1.dp,
                    if (accent) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.border,
                    RoundedCornerShape(50),
                ),
            contentAlignment = Alignment.Center,
        ) {
            TvCrest(item.imageUrl, size = 28.dp, rounded = 3.dp)
        }
        Text(
            text = item.name,
            style = TvMeta,
            color = if (accent) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            textAlign = TextAlign.Center,
        )
    }
}

/**
 * Nothing followed yet. It says how to follow something here rather than sending the reader
 * to the phone: the menu button on any event in the agenda offers its two sides and its
 * competition, which is the whole interaction and needs no keyboard.
 */
@Composable
private fun TvFirstRun() {
    Column(
        Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            Modifier
                .size(84.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, MaterialTheme.colorScheme.border, RoundedCornerShape(50)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = SoccertimeIcons.Star,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.tertiary,
                modifier = Modifier.size(38.dp),
            )
        }
        Text(
            text = stringResource(R.string.first_run_title),
            style = TvScreenTitle,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.padding(top = 20.dp),
        )
        Text(
            text = stringResource(R.string.first_run_body_tv),
            style = TvLabel,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 10.dp).width(520.dp),
        )
    }
}

@Composable
private fun TvFailure(error: ApiError, showingStale: Boolean) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .padding(horizontal = 14.dp, vertical = 9.dp),
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
                "${describeTv(error)} ${stringResource(R.string.showing_stale)}"
            } else {
                describeTv(error)
            },
            style = TvMeta,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
fun describeTv(error: ApiError): String = when (error) {
    is ApiError.Offline -> stringResource(R.string.error_offline)
    is ApiError.RateLimited -> stringResource(R.string.error_rate_limited)
    is ApiError.BadRequest -> error.message
    is ApiError.Http -> stringResource(R.string.error_http, error.code)
    is ApiError.Unexpected -> stringResource(R.string.error_unexpected)
}
