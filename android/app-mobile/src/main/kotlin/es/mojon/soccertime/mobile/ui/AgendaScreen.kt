package es.mojon.soccertime.mobile.ui

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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import es.mojon.soccertime.core.ui.AgendaDay
import es.mojon.soccertime.core.ui.AgendaIntent
import es.mojon.soccertime.core.ui.AgendaFilter
import es.mojon.soccertime.core.ui.anchorPosition
import es.mojon.soccertime.core.ui.AgendaUiState
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.mobile.R
import es.mojon.soccertime.mobile.ui.theme.DayHeadingStyle

@Composable
fun AgendaScreen(
    state: AgendaUiState,
    onIntent: (AgendaIntent) -> Unit,
    onOpen: (EventUi) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxSize()) {
        SearchField(
            query = state.query,
            onQuery = { onIntent(AgendaIntent.Search(it)) },
            modifier = Modifier.padding(start = 14.dp, top = 10.dp, end = 14.dp, bottom = 8.dp),
        )

        Filters(
            state = state,
            onWatchableOnly = { onIntent(AgendaIntent.OnlyWatchable(it)) },
            onClearFilter = { onIntent(AgendaIntent.Narrow(null)) },
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
            state.loading && state.days.isEmpty() -> EmptyState(
                message = stringResource(R.string.loading),
                modifier = Modifier.padding(horizontal = 14.dp),
            )
            state.isEmpty -> EmptyState(
                message = if (state.query.isBlank()) {
                    stringResource(R.string.empty_agenda)
                } else {
                    stringResource(R.string.empty_search)
                },
                modifier = Modifier.padding(horizontal = 14.dp),
            )
            else -> EventList(
                days = state.days,
                trailingCount = state.count,
                canLoadMore = state.canLoadMore,
                onLoadMore = { onIntent(AgendaIntent.LoadMore) },
                onOpen = onOpen,
                anchorId = state.anchorId,
            )
        }
    }
}

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
) {
    val listState = rememberLazyListState()

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
        modifier = modifier.fillMaxSize(),
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

        if (canLoadMore) {
            item(key = "more") {
                Box(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(12.dp))
                        .clickable(onClick = onLoadMore)
                        .padding(vertical = 13.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = stringResource(R.string.load_more),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
    }
}

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
    onWatchableOnly: (Boolean) -> Unit,
    onClearFilter: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
        val filter = state.filter
        if (filter != null) {
            NarrowingChip(filter, onClearFilter)
        } else {
            // The window, stated rather than offered. It was drawn as a chip that looked
            // pressable and answered to nothing; moving between days is a later job, and
            // until it exists this should not pretend to be the control that does it.
            WindowLabel()
        }
        FilterChip(
            label = stringResource(R.string.filter_watchable),
            selected = state.watchableOnly,
            onClick = { onWatchableOnly(!state.watchableOnly) },
        )
    }
}

@Composable
private fun WindowLabel() {
    Row(
        Modifier.height(34.dp).padding(end = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = SoccertimeIcons.Calendar,
            contentDescription = null,
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
