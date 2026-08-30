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
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
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
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.inset
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
import es.mojon.soccertime.core.ui.Crest
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
    /** A panel is over this screen, so nothing here may hold the cursor. */
    covered: Boolean,
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
            TvLoading()
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

        // UP is not absorbed here, because what is above this list is the strip of followed
        // things and reaching it is a move the remote map promises.
        TvEventList(
            days = state.days,
            anchorId = state.anchorId,
            covered = covered,
            onOpen = onOpen,
            onFollow = onFollow,
            absorbing = listOf(FocusDirection.Down, FocusDirection.Right),
            modifier = Modifier.weight(1f),
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
    covered: Boolean,
    onOpen: (EventUi) -> Unit,
    onFollow: (EventUi) -> Unit,
    onLoadMore: () -> Unit,
    onLoadNextDay: () -> Unit,
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
            TvLoading()
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
            covered = covered,
            onOpen = onOpen,
            onFollow = onFollow,
            absorbing = listOf(FocusDirection.Up, FocusDirection.Down, FocusDirection.Right),
            modifier = Modifier.weight(1f),
            // "Ver más" while pages of the day remain, then the day after: the remote's path
            // to the same rule the phone's foot follows — tomorrow is never reachable past an
            // unshown tail of today.
            trailing = when {
                state.canLoadMore -> stringResource(R.string.load_more) to onLoadMore
                state.nextDayLabel != null ->
                    stringResource(R.string.load_next_day, state.nextDayLabel.orEmpty()) to onLoadNextDay
                else -> null
            },
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
        Crest(
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
    covered: Boolean,
    onOpen: (EventUi) -> Unit,
    onFollow: (EventUi) -> Unit,
    absorbing: List<FocusDirection>,
    modifier: Modifier,
    /** A focusable row after the last event — its caption, and what pressing it does. */
    trailing: Pair<String, () -> Unit>? = null,
) {
    val listState = rememberLazyListState()
    val opensHere = remember { FocusRequester() }

    // Where the list opens, and which row the cursor starts on. Both come from the anchor, so
    // they cannot disagree — a list scrolled to the current hour with the cursor on the first
    // row of yesterday would be dragged back to the small hours by one press of the D-pad.
    val opening = remember(days, anchorId) { Opening.of(anchorId, days) }

    // Which row the cursor is on, and which row to put it back on.
    //
    // A panel is an overlay in this same composition: opening one takes the focus into it and
    // closing one destroys the node that held it, leaving the cursor nowhere. The rail still
    // answered — it is outside this group — so the screen looked alive while the list could
    // not be reached at all. Nothing in Compose restores this for us; this version of
    // Foundation has no focus restorer.
    var onRow by remember { mutableStateOf<Int?>(null) }
    var putBackOn by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(days.firstOrNull()?.date, anchorId) {
        if (days.isEmpty()) return@LaunchedEffect
        listState.scrollToItem(opening.index)
        // The anchor is partway down and a lazy list composes from the top, so the row the
        // requester is attached to does not exist until the scroll has been laid out. Asking
        // before then throws, which is how the screen used to open with nothing focused at all.
        takeFocus(opensHere)
    }

    LaunchedEffect(covered) {
        if (covered) {
            // Remembered on the way in, because on the way out the row that had it is gone.
            putBackOn = onRow
        } else if (putBackOn != null) {
            takeFocus(opensHere)
            // Forgotten once used. Left set, the requester stayed tied to a row that may no
            // longer be on the list at all — following something from the panel can remove
            // the very row the panel was opened from.
            putBackOn = null
        }
    }

    LazyColumn(
        state = listState,
        // `weight`, never `fillMaxSize`: the hints below are the only thing that says what the
        // menu button does, and a list that took the whole column pushed them off the screen.
        modifier = modifier.focusEnclosure(absorbing),
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
                    focusRequester = if (event.id == (putBackOn ?: opening.eventId)) {
                        opensHere
                    } else {
                        null
                    },
                    onFocused = { onRow = event.id },
                )
            }
        }

        trailing?.let { (caption, press) ->
            item(key = "trailing") { TvTrailingRow(caption, press) }
        }
    }
}

/** The focusable way past the end of the listing: more of this day, or the next one. */
@Composable
private fun TvTrailingRow(caption: String, onPress: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Box(
        Modifier
            .fillMaxWidth()
            .onFocusChanged { focused = it.isFocused }
            .clip(RoundedCornerShape(12.dp))
            .border(
                2.dp,
                if (focused) MaterialTheme.colorScheme.primary else Color(Palette.HAIRLINE),
                RoundedCornerShape(12.dp),
            )
            .clickable(onClick = onPress)
            .padding(vertical = 14.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = caption,
            style = TvLabel,
            color = if (focused) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/**
 * Which item the list scrolls to and which row takes the cursor. One value, so the two cannot
 * disagree — a list scrolled to the current hour with the cursor on the first row of yesterday
 * would be dragged back to the small hours by one press of the D-pad.
 *
 * Both listings are anchored now, and the anchor is the row nearest to now, so it names
 * something whenever there is anything. The top is only for a list with nothing on it, or one
 * whose anchor has been filtered off it.
 */
private data class Opening(val index: Int, val eventId: Int?) {
    companion object {
        fun of(anchorId: Int?, days: List<AgendaDay>): Opening {
            if (days.isEmpty()) return Opening(0, null)
            val at = anchorPosition(anchorId, days) ?: return Opening(0, days.first().events.firstOrNull()?.id)
            return Opening(at, anchorId)
        }
    }
}

/**
 * Ask for the focus once the row is there to take it.
 *
 * A row that has just been scrolled to, or has just stopped being covered by a panel, is not
 * attached on the frame the request is made, and asking then throws. Retried across a few
 * frames rather than assumed.
 */
private suspend fun takeFocus(requester: FocusRequester) {
    repeat(FOCUS_ATTEMPTS) {
        withFrameNanos { }
        if (runCatching { requester.requestFocus() }.isSuccess) return
    }
}

/** Frames to wait for the row to compose before giving up on focusing it. */
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
            // RIGHT past the last followed thing, and UP above the strip, lead nowhere.
            .focusEnclosure(listOf(FocusDirection.Up, FocusDirection.Right)),
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
            Crest(item.imageUrl, size = 28.dp, rounded = if (competition) 3.dp else 14.dp)
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
/**
 * The first answer takes seconds, and from three metres a muted 14sp line is invisible.
 *
 * The same claim the phone's `LoadingState` makes, drawn by hand because `tv-material` ships
 * no progress indicator: a ring in the palette's loudest green, turning, under a title in the
 * display face. Shared by both listings so they cannot drift apart.
 */
@Composable
private fun TvLoading() {
    val turning = rememberInfiniteTransition(label = "loading")
    val angle by turning.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(durationMillis = 900, easing = LinearEasing)),
        label = "angle",
    )
    Column(
        Modifier.fillMaxWidth().padding(top = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        val ring = MaterialTheme.colorScheme.primary
        val track = Color(Palette.HAIRLINE)
        Canvas(Modifier.size(56.dp)) {
            val stroke = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
            inset(stroke.width / 2) {
                drawArc(color = track, startAngle = 0f, sweepAngle = 360f, useCenter = false, style = stroke)
                drawArc(color = ring, startAngle = angle, sweepAngle = 100f, useCenter = false, style = stroke)
            }
        }
        Text(
            text = stringResource(R.string.loading),
            style = TvHeading,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.padding(top = 18.dp),
        )
        Text(
            text = stringResource(R.string.loading_body),
            style = TvMeta,
            color = Color(Palette.ON_BACKGROUND_MUTED),
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}

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

/**
 * A failure in the reader's terms.
 *
 * `RateLimited` says how long, because both refusals in front of this API send `Retry-After`
 * and they disagree about everything else: Traefik answers `1` from a bucket refilling once a
 * second, the throttle inside answers the rest of its minute — measured at 42. Someone holding
 * a remote decides whether to wait or keep pressing, and "unos segundos" does not tell them.
 * The generic sentence stays for the refusal that arrives without the header.
 */
@Composable
fun describeTv(error: ApiError): String = when (error) {
    is ApiError.Offline -> stringResource(R.string.error_offline)
    is ApiError.RateLimited -> error.retryAfterSeconds
        ?.let { pluralStringResource(R.plurals.error_rate_limited_wait, it.toInt(), it) }
        ?: stringResource(R.string.error_rate_limited)
    is ApiError.BadRequest -> error.message
    is ApiError.Http -> stringResource(R.string.error_http, error.code)
    is ApiError.Unexpected -> stringResource(R.string.error_unexpected)
}
