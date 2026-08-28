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
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.withFrameNanos
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.onFocusChanged
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
import es.mojon.soccertime.core.ui.AgendaFilter
import es.mojon.soccertime.core.ui.AgendaUiState
import es.mojon.soccertime.core.ui.anchorPosition
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.core.ui.FavoritesUiState
import es.mojon.soccertime.core.ui.FollowableKind
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
    onNarrow: (AgendaFilter) -> Unit,
    modifier: Modifier = Modifier,
) {
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

        FollowedStrip(following, onNarrow)

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

        // UP leaves this list, because what is above it is the strip of followed things and
        // reaching it is a move the remote map promises. On the agenda there is nothing above
        // and UP stays put.
        TvEventList(
            days = state.days,
            anchorId = null,
            onOpen = onOpen,
            onFollow = onFollow,
            waysOut = listOf(FocusDirection.Left, FocusDirection.Up),
        )

        TvHints(
            stringResource(R.string.hint_filter_open) to "OK",
            stringResource(R.string.hint_down_to_events) to "▼",
            stringResource(R.string.hint_rail) to "◀",
        )
    }
}

@Composable
fun TvAgendaScreen(
    state: AgendaUiState,
    onOpen: (EventUi) -> Unit,
    onFollow: (EventUi) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(13.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            val filter = state.filter
            if (filter == null) {
                Text(
                    text = stringResource(R.string.tab_agenda),
                    style = TvScreenTitle,
                    color = MaterialTheme.colorScheme.onBackground,
                )
            } else {
                FilterChip(filter)
            }
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

        TvEventList(
            days = state.days,
            anchorId = state.anchorId,
            onOpen = onOpen,
            onFollow = onFollow,
            waysOut = listOf(FocusDirection.Left),
        )

        TvHints(
            stringResource(R.string.hint_open) to "OK ▶",
            stringResource(R.string.hint_follow) to "☰",
            if (state.filter == null) {
                stringResource(R.string.hint_rail) to "◀"
            } else {
                stringResource(R.string.hint_back_to_favorites) to "ATRÁS"
            },
        )
    }
}

/**
 * The filter, standing where the title stood.
 *
 * A second line saying "Agenda" above it would only push the events down: arriving here from a
 * followed team, the thing being shown *is* the title.
 */
@Composable
private fun FilterChip(filter: AgendaFilter) {
    Row(
        Modifier
            .clip(RoundedCornerShape(50))
            .background(Color(Palette.SECONDARY_TINT))
            .border(1.dp, MaterialTheme.colorScheme.secondary, RoundedCornerShape(50))
            .padding(start = 10.dp, top = 7.dp, end = 14.dp, bottom = 7.dp),
        horizontalArrangement = Arrangement.spacedBy(9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TvCrest(
            filter.imageUrl,
            size = 17.dp,
            rounded = if (filter.kind == FollowableKind.Competitions) 2.dp else 8.5.dp,
        )
        Text(
            text = filter.name,
            style = TvLabel,
            color = MaterialTheme.colorScheme.secondary,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/**
 * What the remote can do here, said out loud.
 *
 * ☰ has always followed a team and nothing ever said so, and the play key is new. A D-pad has
 * no hover and no tooltip: an affordance nobody is told about is one nobody uses.
 */
@Composable
private fun TvHints(vararg hints: Pair<String, String>) {
    Row(
        Modifier.fillMaxWidth().padding(top = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        hints.forEach { (what, keys) ->
            Row(
                horizontalArrangement = Arrangement.spacedBy(7.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = keys,
                    style = TvMeta,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier
                        .clip(RoundedCornerShape(5.dp))
                        .border(1.dp, MaterialTheme.colorScheme.border, RoundedCornerShape(5.dp))
                        .padding(horizontal = 6.dp, vertical = 2.dp),
                )
                Text(text = what, style = TvMeta, color = Color(Palette.ON_BACKGROUND_FAINT))
            }
        }
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
    anchorId: Int?,
    onOpen: (EventUi) -> Unit,
    onFollow: (EventUi) -> Unit,
    waysOut: List<FocusDirection>,
) {
    val listState = rememberLazyListState()
    val opensHere = remember { FocusRequester() }

    // Where the list opens, and which row the cursor starts on. Both come from the anchor, so
    // they cannot disagree — a list scrolled to the current hour with the cursor on the first
    // row of yesterday would be dragged back to the small hours by one press of the D-pad.
    val opening = remember(days, anchorId) { Opening.of(anchorId, days) }

    LaunchedEffect(days.firstOrNull()?.date, anchorId) {
        if (days.isEmpty()) return@LaunchedEffect
        listState.scrollToItem(opening.index)
        // The anchor is partway down and a lazy list composes from the top, so the row the
        // requester is attached to does not exist until the scroll has been laid out. Asking
        // before then throws, which is how the screen used to open with nothing focused at all.
        repeat(FOCUS_ATTEMPTS) {
            withFrameNanos { }
            if (runCatching { opensHere.requestFocus() }.isSuccess) return@LaunchedEffect
        }
    }

    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize().focusEnclosure(waysOut),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
        verticalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        days.forEach { day ->
            item(key = "day-${day.date}") { TvDayHeading(day.label) }
            // By position, not by equality. Two events of the same day can be equal as data —
            // the same pair of players at two different times differs only by its id — and
            // comparing them by value attached one `FocusRequester` to several rows, which is
            // undefined and left the remote unable to move between them.
            itemsIndexed(day.events, key = { _, event -> event.id }) { _, event ->
                TvEventRow(
                    event = event,
                    onOpen = { onOpen(event) },
                    onFollow = { onFollow(event) },
                    focusRequester = if (event.id == opening.eventId) opensHere else null,
                )
            }
        }
    }
}

/**
 * Which item the list scrolls to and which row takes the cursor.
 *
 * With no anchor — four in the morning, everything in the window over — it is the end of the
 * list rather than the top: the most recent thing is what is worth being shown, and the top is
 * the small hours of a day already gone.
 */
private data class Opening(val index: Int, val eventId: Int?) {
    companion object {
        fun of(anchorId: Int?, days: List<AgendaDay>): Opening {
            if (days.isEmpty()) return Opening(0, null)
            val at = anchorPosition(anchorId, days)
            if (at != null) return Opening(at, anchorId)
            val items = days.sumOf { 1 + it.events.size }
            return Opening((items - 1).coerceAtLeast(0), days.last().events.lastOrNull()?.id)
        }
    }
}

/** Frames to wait for the scrolled-to row to compose before giving up on focusing it. */
private const val FOCUS_ATTEMPTS = 4

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
 *
 * Each entry is a control now rather than a legend: it opens the agenda narrowed to that team
 * or competition, which was the only reading a press of it ever had.
 */
@Composable
private fun FollowedStrip(following: Following, onNarrow: (AgendaFilter) -> Unit) {
    val entries = following.teams.map { it to FollowableKind.Teams } +
        following.competitions.map { it to FollowableKind.Competitions }
    if (entries.isEmpty()) return

    LazyRow(
        // Room for the halo, which is drawn outside the avatar's own bounds and would
        // otherwise be cut off by the row it lives in.
        modifier = Modifier
            .padding(vertical = 7.dp)
            .focusEnclosure(listOf(FocusDirection.Left, FocusDirection.Down)),
        contentPadding = PaddingValues(horizontal = 7.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        items(entries, key = { (item, kind) -> "$kind-${item.id}" }) { (item, kind) ->
            FollowedAvatar(item, kind) { onNarrow(AgendaFilter(item.id, item.name, item.imageUrl, kind)) }
        }
    }
}

@Composable
private fun FollowedAvatar(item: FollowedItem, kind: FollowableKind, onOpen: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    val interaction = remember { MutableInteractionSource() }
    val competition = kind == FollowableKind.Competitions

    Column(
        Modifier.width(58.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Box(
            Modifier
                .size(48.dp)
                .onFocusChanged { focused = it.isFocused }
                // No `focusable()` beside this: `clickable` is already a focus target, and a
                // second one takes the focus while the first keeps the OK.
                .clickable(interactionSource = interaction, indication = null, onClick = onOpen)
                .cursorHalo(focused, radius = 24.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surface)
                .border(
                    width = if (focused) 2.dp else 1.dp,
                    color = when {
                        focused -> MaterialTheme.colorScheme.primary
                        competition -> MaterialTheme.colorScheme.secondary
                        else -> MaterialTheme.colorScheme.border
                    },
                    shape = RoundedCornerShape(50),
                ),
            contentAlignment = Alignment.Center,
        ) {
            TvCrest(item.imageUrl, size = 28.dp, rounded = if (competition) 3.dp else 14.dp)
        }
        Text(
            text = item.name,
            style = TvMeta,
            color = when {
                focused -> MaterialTheme.colorScheme.primary
                competition -> MaterialTheme.colorScheme.secondary
                else -> MaterialTheme.colorScheme.onSurfaceVariant
            },
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
