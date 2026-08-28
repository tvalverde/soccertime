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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import es.mojon.soccertime.core.ui.FollowableKind
import es.mojon.soccertime.core.ui.FollowableUi
import es.mojon.soccertime.core.ui.ManageIntent
import es.mojon.soccertime.core.ui.ManageUiState
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.mobile.R
import es.mojon.soccertime.mobile.ui.theme.DayHeadingStyle

@Composable
fun ManageFavoritesScreen(
    state: ManageUiState,
    onIntent: (ManageIntent) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth().height(52.dp).padding(horizontal = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(
                    imageVector = SoccertimeIcons.Back,
                    contentDescription = stringResource(R.string.back),
                    tint = MaterialTheme.colorScheme.onBackground,
                )
            }
            Text(
                text = stringResource(R.string.manage_title),
                style = MaterialTheme.typography.titleLarge,
                fontSize = 17.sp,
                color = MaterialTheme.colorScheme.onBackground,
            )
        }

        Segmented(
            kind = state.kind,
            onKind = { onIntent(ManageIntent.Show(it)) },
            modifier = Modifier.padding(start = 14.dp, top = 12.dp, end = 14.dp, bottom = 10.dp),
        )

        SearchField(
            query = state.query,
            onQuery = { onIntent(ManageIntent.Search(it)) },
            modifier = Modifier.padding(horizontal = 14.dp).padding(bottom = 10.dp),
        )

        FollowingSummary(state, Modifier.padding(horizontal = 14.dp).padding(bottom = 10.dp))

        state.error?.let {
            FailureBanner(
                error = it,
                showingStale = false,
                onRetry = { onIntent(ManageIntent.Retry) },
                modifier = Modifier.padding(horizontal = 14.dp).padding(bottom = 8.dp),
            )
        }

        if (state.nothingFound) {
            EmptyState(stringResource(R.string.nothing_found), Modifier.padding(horizontal = 14.dp))
            return@Column
        }

        Row(
            Modifier.fillMaxWidth().padding(start = 14.dp, end = 14.dp, bottom = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = pluralStringResource(R.plurals.results_count, state.total, state.total),
                style = DayHeadingStyle,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Box(Modifier.weight(1f).height(1.dp).background(Color(Palette.HAIRLINE)))
        }

        LazyColumn(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
            items(state.results, key = { it.item.id }) { row ->
                FollowableRow(row) { onIntent(ManageIntent.Follow(row.item, !row.followed, row.kind)) }
            }
        }
    }
}

@Composable
private fun Segmented(kind: FollowableKind, onKind: (FollowableKind) -> Unit, modifier: Modifier = Modifier) {
    Row(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(50))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, Color(Palette.HAIRLINE), RoundedCornerShape(50))
            .padding(4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Segment(stringResource(R.string.tab_teams), kind == FollowableKind.Teams, Modifier.weight(1f)) {
            onKind(FollowableKind.Teams)
        }
        Segment(
            stringResource(R.string.tab_competitions),
            kind == FollowableKind.Competitions,
            Modifier.weight(1f),
        ) {
            onKind(FollowableKind.Competitions)
        }
    }
}

@Composable
private fun Segment(label: String, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    Box(
        modifier
            .height(36.dp)
            .clip(RoundedCornerShape(50))
            .then(if (selected) Modifier.background(MaterialTheme.colorScheme.primary) else Modifier)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 13.sp,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.SemiBold,
        )
    }
}

@Composable
private fun FollowingSummary(state: ManageUiState, modifier: Modifier = Modifier) {
    Row(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = SoccertimeIcons.Star,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.tertiary,
            modifier = Modifier.size(14.dp),
        )
        Text(
            text = stringResource(
                R.string.following_summary,
                pluralStringResource(
                    R.plurals.followed_teams,
                    state.following.teams.size,
                    state.following.teams.size,
                ),
                pluralStringResource(
                    R.plurals.followed_competitions,
                    state.following.competitions.size,
                    state.following.competitions.size,
                ),
            ),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 12.5.sp,
        )
    }
}

@Composable
private fun FollowableRow(row: FollowableUi, onToggle: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .height(58.dp)
            .clickable(onClick = onToggle),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(34.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surface)
                .border(
                    1.dp,
                    if (row.followed) MaterialTheme.colorScheme.outline else Color(Palette.HAIRLINE),
                    RoundedCornerShape(50),
                ),
            contentAlignment = Alignment.Center,
        ) {
            Crest(row.item.imageUrl, size = 22.dp, rounded = 3.dp)
        }
        Text(
            text = row.item.name,
            color = MaterialTheme.colorScheme.onSurface,
            fontSize = 14.5.sp,
            fontWeight = if (row.followed) FontWeight.SemiBold else FontWeight.Normal,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
        Icon(
            imageVector = if (row.followed) SoccertimeIcons.Star else SoccertimeIcons.StarOutline,
            contentDescription = stringResource(
                if (row.followed) R.string.unfollow else R.string.follow,
            ),
            tint = if (row.followed) {
                MaterialTheme.colorScheme.tertiary
            } else {
                Color(Palette.ON_BACKGROUND_MUTED)
            },
            modifier = Modifier.size(21.dp),
        )
    }
}
