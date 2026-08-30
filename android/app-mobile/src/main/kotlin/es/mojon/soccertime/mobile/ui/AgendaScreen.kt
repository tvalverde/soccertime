package es.mojon.soccertime.mobile.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.Velocity
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import es.mojon.soccertime.core.ui.AgendaDay
import es.mojon.soccertime.core.ui.AgendaIntent
import es.mojon.soccertime.core.ui.AgendaFilter
import es.mojon.soccertime.core.ui.Crest
import es.mojon.soccertime.core.ui.anchorPosition
import es.mojon.soccertime.core.ui.AgendaUiState
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.mobile.R
import es.mojon.soccertime.mobile.ui.theme.DayHeadingStyle
import java.time.LocalDate
import kotlin.math.min
import kotlin.math.roundToInt
import kotlinx.coroutines.flow.distinctUntilChanged

@Composable
fun AgendaScreen(
    state: AgendaUiState,
    onIntent: (AgendaIntent) -> Unit,
    onOpen: (EventUi) -> Unit,
    dayLabel: (LocalDate) -> String,
    modifier: Modifier = Modifier,
) {
    var choosingDay by remember { mutableStateOf(false) }

    Column(modifier.fillMaxSize()) {
        SearchField(
            query = state.query,
            onQuery = { onIntent(AgendaIntent.Search(it)) },
            modifier = Modifier.padding(start = 14.dp, top = 10.dp, end = 14.dp, bottom = 8.dp),
        )

        Filters(
            state = state,
            dayLabel = dayLabel,
            onWatchableOnly = { onIntent(AgendaIntent.OnlyWatchable(it)) },
            onClearFilter = { onIntent(AgendaIntent.Narrow(null)) },
            onChooseDay = { choosingDay = true },
            onClearDay = { onIntent(AgendaIntent.PickDay(null)) },
            modifier = Modifier.padding(start = 14.dp, end = 14.dp, bottom = 10.dp),
        )

        state.error?.let {
            FailureBanner(
                error = it,
                showingStale = state.showingStale,
                onRetry = { onIntent(AgendaIntent.Refresh) },
                modifier = Modifier.padding(horizontal = 14.dp).padding(bottom = 8.dp),
            )
        }

        when {
            // The first answer takes seconds, and a blank list for seconds reads as a broken
            // app. Only while there is nothing yet: a refresh must not blank rows already up.
            state.loading && state.days.isEmpty() -> LoadingState(
                Modifier.fillMaxWidth().weight(1f),
            )
            state.isEmpty -> Column(Modifier.weight(1f)) {
                EmptyState(
                    message = if (state.query.isBlank()) {
                        stringResource(R.string.empty_agenda)
                    } else {
                        stringResource(R.string.empty_search)
                    },
                    modifier = Modifier.padding(horizontal = 14.dp),
                )
                // A day with nothing on it still leads somewhere: the chosen day may simply
                // be quiet, and the way onward should not require reopening the calendar.
                state.nextDayLabel?.let {
                    NextDayFoot(
                        label = it,
                        loading = false,
                        progress = 0f,
                        armed = false,
                        onLoad = { onIntent(AgendaIntent.LoadNextDay) },
                    )
                }
            }
            else -> EventList(
                days = state.days,
                trailingCount = state.count,
                canLoadMore = state.canLoadMore,
                // Paused while a failure stands: parked at the end of the listing, an
                // unconditional ask would retry against the rate limit for as long as the
                // reader stared at it. The banner's own Retry is the way back.
                onLoadMore = { if (state.error == null) onIntent(AgendaIntent.LoadMore) },
                loadingMore = state.loading,
                onOpen = onOpen,
                anchorId = state.anchorId,
                nextDayLabel = state.nextDayLabel.takeIf { !state.canLoadMore },
                loadingNextDay = state.loading,
                onLoadNextDay = { onIntent(AgendaIntent.LoadNextDay) },
            )
        }
    }

    if (choosingDay) {
        DayPickerDialog(
            shown = state.day,
            onPick = { day ->
                choosingDay = false
                onIntent(AgendaIntent.PickDay(day))
            },
            onDismiss = { choosingDay = false },
        )
    }
}

/**
 * The calendar, as a dialog over the listing.
 *
 * `DatePickerState` speaks in millis at UTC midnight, so the conversion is a whole number of
 * days in both directions and no zone can shift it.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DayPickerDialog(shown: LocalDate, onPick: (LocalDate) -> Unit, onDismiss: () -> Unit) {
    val picker = rememberDatePickerState(initialSelectedDateMillis = shown.toEpochDay() * MILLIS_PER_DAY)
    DatePickerDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton(
                onClick = {
                    picker.selectedDateMillis?.let { onPick(LocalDate.ofEpochDay(it / MILLIS_PER_DAY)) }
                },
            ) {
                Text(stringResource(R.string.pick_day_confirm))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.pick_day_cancel)) }
        },
    ) {
        DatePicker(state = picker, showModeToggle = false)
    }
}

private const val MILLIS_PER_DAY = 86_400_000L

@Composable
fun EventList(
    days: List<AgendaDay>,
    trailingCount: Int,
    canLoadMore: Boolean,
    onLoadMore: () -> Unit,
    onOpen: (EventUi) -> Unit,
    modifier: Modifier = Modifier,
    /**
     * The event to open on: the first that has not finished. The list spans yesterday and
     * today, so its top is the small hours of a day already gone — scrolling there and asking
     * the reader to find the present would be the wrong end of a hundred and sixty rows.
     */
    anchorId: Int? = null,
    /** The foot that loads the day after the listing's end; null draws no foot at all. */
    nextDayLabel: String? = null,
    loadingNextDay: Boolean = false,
    onLoadNextDay: () -> Unit = {},
    /** Whether a page of the current day is on its way, which draws the quiet row. */
    loadingMore: Boolean = false,
) {
    val listState = rememberLazyListState()

    // "Estirar hacia arriba": drag that keeps pulling once the list has no more to give
    // reaches this connection as unconsumed scroll. The gesture is visible while it is made —
    // the listing rides up with the finger, at half a pixel per pixel, while the foot's ring
    // fills — and it fires on RELEASE with the ring full, never mid-drag. The foot is also
    // plainly tappable, so the feature exists before the gesture is found.
    val threshold = with(LocalDensity.current) { PULL_TO_LOAD_DISTANCE.toPx() }
    val pull = remember(nextDayLabel != null, threshold) {
        PullPastTheEnd(threshold, onLoadNextDay)
    }
    val ride by animateFloatAsState(
        targetValue = pull.stretch * PULL_GIVE,
        // Snapped to the finger while dragging; sprung back home when it lets go.
        animationSpec = if (pull.dragging) snap() else spring(),
        label = "pull",
    )
    val haptics = LocalHapticFeedback.current
    LaunchedEffect(pull.armed) {
        if (pull.armed) haptics.performHapticFeedback(HapticFeedbackType.LongPress)
    }

    // The next page asks for itself as the last rows of this one come into view, so in a
    // normal scroll it has already arrived and there is no seam — and no button.
    if (canLoadMore) {
        LaunchedEffect(listState, days) {
            snapshotFlow {
                val info = listState.layoutInfo
                (info.visibleItemsInfo.lastOrNull()?.index ?: 0) >= info.totalItemsCount - PREFETCH_AHEAD
            }
                .distinctUntilChanged()
                .collect { nearTheEnd -> if (nearTheEnd) onLoadMore() }
        }
    }

    // The top when there is no anchor, which now means only an empty listing or one whose
    // anchor has been filtered off it. Falling through to the *last* item is what sent the
    // favourites screen, which passed no anchor at all, to the bottom of its own list.
    val opensOn = remember(days, anchorId) { anchorPosition(anchorId, days) ?: 0 }
    LaunchedEffect(days.firstOrNull()?.date, anchorId) {
        // Not wrapped in `runCatching`: that is a suspending call, and catching everything
        // around one swallows its cancellation — which is precisely the mistake that let an
        // abandoned load go on to publish its answer.
        if (days.isNotEmpty()) listState.scrollToItem(opensOn.coerceAtLeast(0))
    }

    LazyColumn(
        state = listState,
        modifier = modifier
            .fillMaxSize()
            .then(if (nextDayLabel != null) Modifier.nestedScroll(pull) else Modifier)
            .offset { IntOffset(0, -ride.roundToInt()) },
        contentPadding = androidx.compose.foundation.layout.PaddingValues(
            start = 14.dp,
            end = 14.dp,
            bottom = 16.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        days.forEach { day ->
            item(key = "day-${day.date}") {
                DayHeading(day.label, if (day == days.first()) trailingCount else 0)
            }
            items(day.events, key = { it.id }) { event ->
                EventCard(event = event, onPlay = { onOpen(event) })
            }
        }

        if (nextDayLabel != null) {
            item(key = "next-day") {
                NextDayFoot(
                    label = nextDayLabel,
                    loading = loadingNextDay,
                    progress = pull.progress,
                    armed = pull.armed,
                    onLoad = onLoadNextDay,
                )
            }
        }

        if (canLoadMore && loadingMore) {
            item(key = "loading-more") {
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 14.dp),
                    horizontalArrangement = Arrangement.spacedBy(9.dp, Alignment.CenterHorizontally),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    CircularProgressIndicator(
                        color = MaterialTheme.colorScheme.primary,
                        trackColor = Color(Palette.HAIRLINE),
                        strokeWidth = 2.5.dp,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        text = stringResource(R.string.loading_more),
                        fontSize = 11.sp,
                        color = Color(Palette.ON_BACKGROUND_FAINT),
                    )
                }
            }
        }
    }
}

/**
 * The end of the listing, naming the day it can become.
 *
 * Drawn only when the current day is exhausted — tomorrow must not be reachable past an
 * unshown tail of today — and reached two ways: the pull past the end, and a plain press.
 */
@Composable
private fun NextDayFoot(
    label: String,
    loading: Boolean,
    progress: Float,
    armed: Boolean,
    onLoad: () -> Unit,
) {
    val accent = if (armed) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
    Column(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onLoad)
            .padding(top = 14.dp, bottom = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Box(contentAlignment = Alignment.Center) {
            if (loading) {
                CircularProgressIndicator(
                    color = MaterialTheme.colorScheme.primary,
                    trackColor = Color(Palette.HAIRLINE),
                    strokeWidth = 2.5.dp,
                    modifier = Modifier.size(38.dp),
                )
            } else {
                if (armed) {
                    Box(
                        Modifier
                            .size(38.dp)
                            .clip(RoundedCornerShape(50))
                            .background(Color(Palette.PRIMARY_TINT)),
                    )
                }
                CircularProgressIndicator(
                    progress = { progress },
                    color = accent,
                    trackColor = Color(Palette.HAIRLINE),
                    strokeWidth = 2.5.dp,
                    modifier = Modifier.size(38.dp),
                )
            }
            Icon(
                imageVector = SoccertimeIcons.ArrowUp,
                contentDescription = null,
                tint = accent,
                modifier = Modifier.size(16.dp),
            )
        }
        Text(text = label, style = DayHeadingStyle, color = accent)
        Text(
            text = stringResource(if (armed) R.string.next_day_release else R.string.next_day_hint),
            fontSize = 11.sp,
            color = if (armed) accent else Color(Palette.ON_BACKGROUND_FAINT),
        )
    }
}

/**
 * The pull, made visible and fired on release.
 *
 * Upward drag the list cannot consume — which only happens at its end — accumulates as
 * [stretch]; dragging back down pays it off before the list moves again, so the gesture can
 * be walked out of. Crossing [threshold] arms it; the trigger is the finger LEAVING while
 * armed, reported here as the pre-fling, so nothing fires mid-thought and letting the
 * listing settle back is always one small drag away.
 */
private class PullPastTheEnd(
    private val threshold: Float,
    private val onRelease: () -> Unit,
) : NestedScrollConnection {

    var stretch by mutableStateOf(0f)
        private set
    var dragging by mutableStateOf(false)
        private set

    val armed: Boolean get() = stretch >= threshold
    val progress: Float get() = (stretch / threshold).coerceIn(0f, 1f)

    override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
        if (source == NestedScrollSource.UserInput && available.y > 0f && stretch > 0f) {
            val takenBack = min(available.y, stretch)
            stretch -= takenBack
            return Offset(0f, takenBack)
        }
        return Offset.Zero
    }

    override fun onPostScroll(consumed: Offset, available: Offset, source: NestedScrollSource): Offset {
        if (source == NestedScrollSource.UserInput && available.y < 0f) {
            dragging = true
            stretch = (stretch - available.y).coerceAtMost(threshold * PULL_OVERSHOOT)
            return Offset(0f, available.y)
        }
        return Offset.Zero
    }

    override suspend fun onPreFling(available: Velocity): Velocity {
        val hadStretch = stretch > 0f
        val fire = armed
        dragging = false
        stretch = 0f
        if (fire) onRelease()
        // A gesture that was spent stretching must not also fling the list.
        return if (hadStretch) available else Velocity.Zero
    }
}

/** Raw upward drag past the end before the pull arms; the ride shows half of it. */
private val PULL_TO_LOAD_DISTANCE = 112.dp

/** The listing follows the finger at half a pixel per pixel: movement, with resistance. */
private const val PULL_GIVE = 0.5f

/** How far past armed the stretch may grow, so the ride stops instead of running away. */
private const val PULL_OVERSHOOT = 1.5f

/** Rows left below the viewport when the next page of the day is asked for. */
private const val PREFETCH_AHEAD = 10

@Composable
private fun DayHeading(label: String, count: Int) {
    Row(
        Modifier.fillMaxWidth().padding(top = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text = label, style = DayHeadingStyle, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Box(Modifier.weight(1f).height(1.dp).background(Color(Palette.HAIRLINE)))
        if (count > 0) {
            Text(
                text = pluralStringResource(R.plurals.with_link_count, count, count),
                color = Color(Palette.ON_BACKGROUND_FAINT),
                fontSize = 10.5.sp,
            )
        }
    }
}

@Composable
fun SearchField(query: String, onQuery: (String) -> Unit, modifier: Modifier = Modifier) {
    TextField(
        value = query,
        onValueChange = onQuery,
        singleLine = true,
        placeholder = {
            Text(
                text = stringResource(R.string.search_hint),
                color = Color(Palette.ON_BACKGROUND_FAINT),
                fontSize = 14.sp,
            )
        },
        leadingIcon = {
            Icon(
                imageVector = SoccertimeIcons.Search,
                contentDescription = null,
                tint = Color(Palette.ON_BACKGROUND_MUTED),
                modifier = Modifier.size(18.dp),
            )
        },
        trailingIcon = if (query.isEmpty()) {
            null
        } else {
            {
                Icon(
                    imageVector = SoccertimeIcons.Close,
                    contentDescription = stringResource(R.string.clear_search),
                    tint = Color(Palette.ON_BACKGROUND_MUTED),
                    modifier = Modifier.size(18.dp).clickable { onQuery("") },
                )
            }
        },
        shape = RoundedCornerShape(12.dp),
        colors = TextFieldDefaults.colors(
            focusedContainerColor = MaterialTheme.colorScheme.surface,
            unfocusedContainerColor = MaterialTheme.colorScheme.surface,
            focusedIndicatorColor = Color.Transparent,
            unfocusedIndicatorColor = Color.Transparent,
        ),
        modifier = modifier.fillMaxWidth(),
    )
}

@Composable
private fun Filters(
    state: AgendaUiState,
    dayLabel: (LocalDate) -> String,
    onWatchableOnly: (Boolean) -> Unit,
    onClearFilter: () -> Unit,
    onChooseDay: () -> Unit,
    onClearDay: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        val filter = state.filter
        if (filter != null) {
            NarrowingChip(filter, onClearFilter)
        }
        DayChip(
            chosen = state.chosenDay?.let(dayLabel),
            onChoose = onChooseDay,
            onClear = onClearDay,
        )
        FilterChip(
            label = stringResource(R.string.filter_watchable),
            selected = state.watchableOnly,
            onClick = { onWatchableOnly(!state.watchableOnly) },
        )
    }
}

/**
 * The way into the calendar, and the day it chose.
 *
 * This used to be a bare label, deliberately: a chip that looked pressable and answered to
 * nothing. Now it answers — pressing it opens the calendar — and once a day is chosen it
 * takes the same voice as the narrowing chip, cross included, because it has become the same
 * kind of thing: a filter the reader applied and can take off.
 */
@Composable
private fun DayChip(chosen: String?, onChoose: () -> Unit, onClear: () -> Unit) {
    if (chosen == null) {
        Row(
            Modifier
                .height(34.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, Color(Palette.HAIRLINE), RoundedCornerShape(50))
                .clickable(onClick = onChoose)
                .padding(horizontal = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = SoccertimeIcons.Calendar,
                contentDescription = stringResource(R.string.pick_day),
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(14.dp),
            )
            Text(
                text = stringResource(R.string.filter_today),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 12.5.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
    } else {
        Row(
            Modifier
                .height(34.dp)
                .clip(RoundedCornerShape(50))
                .background(Color(Palette.SECONDARY_TINT))
                .border(1.dp, MaterialTheme.colorScheme.secondary, RoundedCornerShape(50))
                .clickable(onClick = onChoose)
                .padding(start = 10.dp, end = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = SoccertimeIcons.Calendar,
                contentDescription = stringResource(R.string.pick_day),
                tint = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.size(14.dp),
            )
            Text(
                text = chosen,
                color = MaterialTheme.colorScheme.secondary,
                fontSize = 12.5.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
            )
            Icon(
                imageVector = SoccertimeIcons.Close,
                contentDescription = stringResource(R.string.pick_day_clear),
                tint = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.size(14.dp).clickable(onClick = onClear),
            )
        }
    }
}

/**
 * The followed thing the agenda is narrowed to.
 *
 * It carries the crest and the name — the value, not the kind — because "Competición" would
 * read as a category filter rather than as the competition the reader pressed. The cross is
 * how it is undone, and system BACK does the same thing.
 */
@Composable
private fun NarrowingChip(filter: AgendaFilter, onClear: () -> Unit) {
    Row(
        Modifier
            .height(34.dp)
            .clip(RoundedCornerShape(50))
            .background(Color(Palette.SECONDARY_TINT))
            .border(1.dp, MaterialTheme.colorScheme.secondary, RoundedCornerShape(50))
            .clickable(onClick = onClear)
            .padding(start = 7.dp, end = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Crest(filter.imageUrl, size = 18.dp, rounded = 3.dp)
        Text(
            text = filter.name,
            color = MaterialTheme.colorScheme.secondary,
            fontSize = 12.5.sp,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f, fill = false),
        )
        Icon(
            imageVector = SoccertimeIcons.Close,
            contentDescription = stringResource(R.string.clear_filter),
            tint = MaterialTheme.colorScheme.secondary,
            modifier = Modifier.size(14.dp),
        )
    }
}

@Composable
private fun FilterChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    leading: androidx.compose.ui.graphics.vector.ImageVector? = null,
) {
    Row(
        Modifier
            .height(34.dp)
            .clip(RoundedCornerShape(50))
            .then(
                if (selected) {
                    Modifier.background(MaterialTheme.colorScheme.primary)
                } else {
                    Modifier
                        .background(MaterialTheme.colorScheme.surface)
                        .border(1.dp, Color(Palette.HAIRLINE), RoundedCornerShape(50))
                },
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        leading?.let {
            Icon(
                imageVector = it,
                contentDescription = null,
                tint = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(14.dp),
            )
        }
        Text(
            text = label,
            color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 12.5.sp,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.SemiBold,
        )
    }
}
