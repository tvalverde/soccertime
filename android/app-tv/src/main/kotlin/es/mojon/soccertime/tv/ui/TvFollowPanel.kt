package es.mojon.soccertime.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Icon
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import es.mojon.soccertime.core.data.Favorites
import es.mojon.soccertime.core.ui.Followable
import es.mojon.soccertime.core.ui.FollowableKind
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.tv.R
import es.mojon.soccertime.tv.ui.theme.TvHeading
import es.mojon.soccertime.tv.ui.theme.TvLabel
import es.mojon.soccertime.tv.ui.theme.TvMeta

/**
 * Following something, from the event that made you want to.
 *
 * A match names three things a reader might mean — the two sides and the competition — so
 * rather than guessing, all of them are offered with their current state and OK toggles one.
 * That is also the only interaction on this screen that needs no keyboard: every name is
 * already on the television, and choosing between three is what a D-pad is good at.
 *
 * Opened with the remote's menu button from any row, including the rows with nothing to play.
 * Those are most of the agenda, and a team whose match carries no link is exactly the sort of
 * thing somebody wants to follow.
 */
@Composable
fun TvFollowPanel(
    title: String,
    candidates: List<Followable>,
    following: Favorites,
    onToggle: (Followable, Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val first = remember { FocusRequester() }
    LaunchedEffect(title) { runCatching { first.requestFocus() } }

    Box(
        modifier.fillMaxSize().background(Color(Palette.SCRIM)),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            Modifier
                .width(560.dp)
                // The same reason as the links panel: an overlay in this composition, with a
                // list of rows behind it that are still focus targets. ATRÁS is the way out.
                .focusEnclosure(EveryDirection)
                .clip(RoundedCornerShape(18.dp))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, MaterialTheme.colorScheme.border, RoundedCornerShape(18.dp))
                .padding(vertical = 22.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = stringResource(R.string.follow_title),
                style = TvHeading,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 24.dp, bottom = 4.dp),
            )
            Text(
                text = title,
                style = TvLabel,
                fontSize = 13.sp,
                color = Color(Palette.ON_BACKGROUND_FAINT),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(start = 24.dp, end = 24.dp, bottom = 10.dp),
            )

            candidates.forEachIndexed { index, candidate ->
                val followed = when (candidate.kind) {
                    FollowableKind.Teams -> candidate.item.id in following.teamIds
                    FollowableKind.Competitions -> candidate.item.id in following.competitionIds
                }
                FollowRow(
                    candidate = candidate,
                    followed = followed,
                    focusRequester = if (index == 0) first else null,
                    onToggle = { onToggle(candidate, !followed) },
                )
            }

            Text(
                text = stringResource(R.string.back_to_return),
                style = TvMeta,
                color = Color(Palette.ON_BACKGROUND_FAINT),
                modifier = Modifier.padding(start = 24.dp, top = 12.dp),
            )
        }
    }
}

@Composable
private fun FollowRow(
    candidate: Followable,
    followed: Boolean,
    focusRequester: FocusRequester?,
    onToggle: () -> Unit,
) {
    var focused by remember { mutableStateOf(false) }
    val interaction = remember { MutableInteractionSource() }

    Row(
        Modifier
            .fillMaxWidth()
            .height(56.dp)
            .then(focusRequester?.let { Modifier.focusRequester(it) } ?: Modifier)
            .onFocusChanged { focused = it.isFocused }
            .clickable(interactionSource = interaction, indication = null, onClick = onToggle)
            .background(if (focused) Color(Palette.CARD_BORDER) else Color.Transparent)
            .padding(horizontal = 24.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(38.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.background)
                .border(1.dp, MaterialTheme.colorScheme.border, RoundedCornerShape(50)),
            contentAlignment = Alignment.Center,
        ) {
            TvCrest(candidate.item.imageUrl, size = 24.dp, rounded = 3.dp)
        }

        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                text = candidate.item.name,
                style = TvLabel,
                fontSize = 16.sp,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = stringResource(
                    when (candidate.kind) {
                        FollowableKind.Teams -> R.string.kind_team
                        FollowableKind.Competitions -> R.string.kind_competition
                    },
                ),
                style = TvMeta,
                fontSize = 11.sp,
                color = Color(Palette.ON_BACKGROUND_MUTED),
            )
        }

        Icon(
            imageVector = if (followed) SoccertimeIcons.Star else SoccertimeIcons.StarOutline,
            contentDescription = stringResource(if (followed) R.string.unfollow else R.string.follow),
            tint = if (followed) {
                MaterialTheme.colorScheme.tertiary
            } else {
                Color(Palette.ON_BACKGROUND_MUTED)
            },
            modifier = Modifier.size(24.dp),
        )
    }
}
