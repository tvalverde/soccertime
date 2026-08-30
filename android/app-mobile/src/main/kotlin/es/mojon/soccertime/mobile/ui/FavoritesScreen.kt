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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import es.mojon.soccertime.core.data.FollowedItem
import es.mojon.soccertime.core.data.Following
import es.mojon.soccertime.core.data.FontScale
import es.mojon.soccertime.core.ui.AgendaFilter
import es.mojon.soccertime.core.ui.Crest
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.core.ui.FollowableKind
import es.mojon.soccertime.core.ui.FavoritesIntent
import es.mojon.soccertime.core.ui.FavoritesUiState
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.mobile.R

@Composable
fun FavoritesScreen(
    state: FavoritesUiState,
    following: Following,
    fontScale: FontScale,
    onIntent: (FavoritesIntent) -> Unit,
    onFontScale: (FontScale) -> Unit,
    onEdit: () -> Unit,
    onBrowseAgenda: () -> Unit,
    onOpen: (EventUi) -> Unit,
    onNarrow: (AgendaFilter) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (state.chosenNothing) {
        FirstRun(onChoose = onEdit, onBrowse = onBrowseAgenda, modifier = modifier)
        return
    }

    Column(modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth().padding(start = 14.dp, top = 14.dp, end = 14.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = stringResource(R.string.favorites_title),
                style = MaterialTheme.typography.headlineMedium,
                fontSize = 25.sp,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Box(Modifier.weight(1f))
            FontSizeButton(fontScale, onFontScale)
        }

        FollowedStrip(following = following, onEdit = onEdit, onNarrow = onNarrow)

        state.error?.let {
            FailureBanner(
                error = it,
                showingStale = state.showingStale,
                onRetry = { onIntent(FavoritesIntent.Refresh) },
                modifier = Modifier.padding(horizontal = 14.dp).padding(bottom = 8.dp),
            )
        }

        if (state.loading && state.days.isEmpty()) {
            LoadingState(Modifier.fillMaxWidth().weight(1f))
        } else if (state.nothingComingUp) {
            EmptyState(stringResource(R.string.nothing_coming_up), Modifier.padding(horizontal = 14.dp))
        } else {
            EventList(
                days = state.days,
                trailingCount = 0,
                canLoadMore = false,
                onLoadMore = { },
                onOpen = onOpen,
                anchorId = state.anchorId,
            )
        }
    }
}

/**
 * The three text sizes, in the spot the Editar button used to hold.
 *
 * That button went because it duplicated the (+) tile at the end of the strip — two controls
 * to the same screen — and what replaced it answers something nothing else did. The options
 * are drawn as the letter at its own size, because "Pequeño" written small *is* the choice
 * being offered and a word beside it would only restate it.
 */
@Composable
private fun FontSizeButton(scale: FontScale, onScale: (FontScale) -> Unit) {
    var open by remember { mutableStateOf(false) }
    val label = stringResource(R.string.font_size)
    Box {
        Row(
            Modifier
                .height(34.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(50))
                .clickable(onClick = { open = true })
                .semantics { contentDescription = label }
                .padding(horizontal = 13.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "A",
                color = Color(Palette.ON_BACKGROUND_MUTED),
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = "a",
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 15.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            Row(
                Modifier.padding(horizontal = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                FontSizeOption(FontScale.SMALL, R.string.font_small, 13.sp, scale) { onScale(it); open = false }
                FontSizeOption(FontScale.MEDIUM, R.string.font_medium, 16.sp, scale) { onScale(it); open = false }
                FontSizeOption(FontScale.LARGE, R.string.font_large, 20.sp, scale) { onScale(it); open = false }
            }
        }
    }
}

@Composable
private fun FontSizeOption(
    option: FontScale,
    nameRes: Int,
    letterSize: TextUnit,
    current: FontScale,
    onScale: (FontScale) -> Unit,
) {
    val chosen = option == current
    val name = stringResource(nameRes)
    Box(
        Modifier
            .size(48.dp)
            .clip(RoundedCornerShape(10.dp))
            .then(
                if (chosen) {
                    Modifier
                        .background(Color(Palette.PRIMARY_TINT))
                        .border(1.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(10.dp))
                } else {
                    Modifier
                },
            )
            .clickable(onClick = { onScale(option) })
            .semantics { contentDescription = name },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "A",
            color = if (chosen) MaterialTheme.colorScheme.primary else Color(Palette.ON_BACKGROUND_MUTED),
            fontSize = letterSize,
            fontWeight = if (chosen) FontWeight.Bold else FontWeight.SemiBold,
        )
    }
}

/**
 * The row of what the reader follows, drawn from the store alone — the names and crests are
 * kept beside the ids for exactly this, so the screen the app opens on needs no request and
 * appears before the first response arrives.
 */
/** Wide enough that two favourites with a shared prefix do not read as the same one. */
private val FOLLOWED_TILE = 66.dp

@Composable
private fun FollowedStrip(
    following: Following,
    onEdit: () -> Unit,
    onNarrow: (AgendaFilter) -> Unit,
) {
    val entries = following.teams.map { it to FollowableKind.Teams } +
        following.competitions.map { it to FollowableKind.Competitions }
    LazyRow(
        Modifier.fillMaxWidth().padding(start = 14.dp, end = 14.dp, bottom = 14.dp),
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        items(entries, key = { (item, kind) -> "$kind-${item.id}" }) { (item, kind) ->
            FollowedAvatar(item, kind) {
                onNarrow(AgendaFilter(item.id, item.name, item.imageUrl, kind))
            }
        }
        item(key = "add") {
            Column(
                Modifier.width(FOLLOWED_TILE).clickable(onClick = onEdit),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Box(
                    Modifier
                        .size(46.dp)
                        .clip(RoundedCornerShape(50))
                        .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(50)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = SoccertimeIcons.Add,
                        contentDescription = null,
                        tint = Color(Palette.ON_BACKGROUND_MUTED),
                        modifier = Modifier.size(20.dp),
                    )
                }
                Text(
                    text = stringResource(R.string.edit),
                    color = Color(Palette.ON_BACKGROUND_FAINT),
                    fontSize = 9.5.sp,
                    maxLines = 1,
                )
            }
        }
    }
}

/**
 * One followed thing, and a way into its agenda.
 *
 * It was a legend before, which left a row of crests on the screen the app opens on that
 * answered to nothing. A press has only ever had one reading: show me this team.
 */
@Composable
private fun FollowedAvatar(item: FollowedItem, kind: FollowableKind, onNarrow: () -> Unit) {
    val accent = kind == FollowableKind.Competitions
    Column(
        Modifier.width(FOLLOWED_TILE).clickable(onClick = onNarrow),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Box(
            Modifier
                .size(46.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surface)
                .border(
                    1.dp,
                    if (accent) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.outline,
                    RoundedCornerShape(50),
                ),
            contentAlignment = Alignment.Center,
        ) {
            Crest(item.imageUrl, size = 26.dp, rounded = if (accent) 3.dp else 13.dp)
        }
        Text(
            text = item.name,
            color = if (accent) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 9.5.sp,
            lineHeight = 11.5.sp,
            // Two lines, because on one at this width "FC Barcelona" and "FC Barcelona
            // Femenino" both truncate to "FC Barc…" — two different things a reader follows,
            // drawn as the same label, in a strip whose whole job is telling them apart.
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            textAlign = TextAlign.Center,
        )
    }
}

/**
 * What a fresh install opens on. It asks for nothing over the network — the view model makes
 * no request while nothing is followed — so this renders before the device has been online.
 */
@Composable
private fun FirstRun(onChoose: () -> Unit, onBrowse: () -> Unit, modifier: Modifier = Modifier) {
    Column(
        modifier.fillMaxSize().padding(horizontal = 34.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            Modifier
                .size(84.dp)
                .clip(RoundedCornerShape(50))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(50)),
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
            style = MaterialTheme.typography.headlineMedium,
            fontSize = 25.sp,
            color = MaterialTheme.colorScheme.onBackground,
            textAlign = TextAlign.center(),
            modifier = Modifier.padding(top = 20.dp),
        )
        Text(
            text = stringResource(R.string.first_run_body),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 14.sp,
            lineHeight = 21.sp,
            textAlign = TextAlign.center(),
            modifier = Modifier.padding(top = 10.dp),
        )

        Box(
            Modifier
                .padding(top = 26.dp)
                .fillMaxWidth()
                .height(48.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(MaterialTheme.colorScheme.primary)
                .clickable(onClick = onChoose),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = stringResource(R.string.first_run_choose),
                color = MaterialTheme.colorScheme.onPrimary,
                fontSize = 14.5.sp,
                fontWeight = FontWeight.Bold,
            )
        }
        Box(
            Modifier.fillMaxWidth().height(46.dp).clickable(onClick = onBrowse),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = stringResource(R.string.first_run_browse),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

private fun TextAlign.Companion.center() = Center
