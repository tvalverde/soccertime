package es.mojon.soccertime.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Icon
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import coil3.compose.AsyncImage
import es.mojon.soccertime.core.ui.ChannelChip
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.Side
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.tv.R
import es.mojon.soccertime.tv.ui.theme.TvEventTime
import es.mojon.soccertime.tv.ui.theme.TvMeta
import es.mojon.soccertime.tv.ui.theme.TvTeamName

/**
 * One event, across the width of a television.
 *
 * A row and not the phone's stacked card: there is room here to set both sides on one line,
 * and a list read from three metres wants fewer lines and larger ones.
 *
 * Focus is drawn rather than delegated. `tv-material`'s `Surface` brings its own scale and
 * glow, and the design settled on a 2 dp neon border with a soft halo — trying to bend the
 * component into that costs more than drawing it, and the halo has to sit outside the row's
 * bounds, which is why the list that holds these must not clip.
 */
@Composable
fun TvEventRow(
    event: EventUi,
    onOpen: () -> Unit,
    modifier: Modifier = Modifier,
    focusRequester: FocusRequester? = null,
) {
    var focused by remember { mutableStateOf(false) }
    val interaction = remember { MutableInteractionSource() }
    val gold = MaterialTheme.colorScheme.tertiary

    Row(
        modifier
            .fillMaxWidth()
            .height(ROW_HEIGHT)
            .then(focusRequester?.let { Modifier.focusRequester(it) } ?: Modifier)
            .onFocusChanged { focused = it.isFocused }
            // No `focusable()` beside this. `clickable` is already a focus target, and
            // adding another puts the focus on the outer one while the inner one is what
            // handles OK — which is a control the remote can highlight and never activate.
            .clickable(interactionSource = interaction, indication = null, onClick = onOpen)
            .clip(RoundedCornerShape(RADIUS))
            .background(
                if (focused) Color(Palette.CARD_BORDER) else MaterialTheme.colorScheme.surface,
            )
            .border(
                width = if (focused) 2.dp else 1.dp,
                color = if (focused) MaterialTheme.colorScheme.primary else Color(Palette.CARD_BORDER),
                shape = RoundedCornerShape(RADIUS),
            )
            .then(
                if (event.favorite) {
                    Modifier.drawBehind {
                        drawRect(color = gold, size = Size(FAVOURITE_EDGE.toPx(), size.height))
                    }
                } else {
                    Modifier
                },
            )
            .padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.width(74.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                text = event.time,
                style = TvEventTime,
                color = if (event.live) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
            )
            if (event.live) {
                Text(
                    text = stringResource(R.string.live),
                    color = MaterialTheme.colorScheme.onPrimary,
                    fontSize = 9.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.5.sp,
                    modifier = Modifier
                        .clip(RoundedCornerShape(50))
                        .background(MaterialTheme.colorScheme.primary)
                        .padding(horizontal = 6.dp, vertical = 2.dp),
                )
            }
        }

        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            if (event.title != null) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = event.title.orEmpty(),
                        style = TvTeamName,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    event.details?.let {
                        Text(it, style = TvMeta, color = Color(Palette.ON_BACKGROUND_FAINT), maxLines = 1)
                    }
                }
            } else {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    SideOnOneLine(event.home)
                    Text("—", style = TvMeta, color = Color(Palette.ON_BACKGROUND_FAINT))
                    SideOnOneLine(event.away)
                }
            }

            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TvCrest(event.flagUrl, size = 12.dp, rounded = 2.dp)
                Text(
                    text = event.competition,
                    style = TvMeta,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )
                Text(
                    text = event.sport,
                    style = TvMeta,
                    fontSize = 11.sp,
                    letterSpacing = 0.6.sp,
                    color = Color(Palette.ON_BACKGROUND_FAINT),
                    maxLines = 1,
                )
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
            event.channels.forEach { TvChannelPill(it) }
            if (event.hiddenChannels > 0) {
                Text(
                    text = "+${event.hiddenChannels}",
                    style = TvMeta,
                    color = Color(Palette.ON_BACKGROUND_MUTED),
                )
            }
        }

        // Nothing at all when there is nothing to open. An empty ring is a control the eye
        // looks for a meaning in and does not find one.
        if (event.openable) {
            Box(
                Modifier
                    .size(42.dp)
                    .clip(RoundedCornerShape(50))
                    .then(
                        if (focused) {
                            Modifier.background(MaterialTheme.colorScheme.primary)
                        } else {
                            Modifier.border(1.dp, MaterialTheme.colorScheme.border, RoundedCornerShape(50))
                        },
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = SoccertimeIcons.Play,
                    contentDescription = stringResource(R.string.play),
                    tint = if (focused) {
                        MaterialTheme.colorScheme.onPrimary
                    } else {
                        MaterialTheme.colorScheme.primary
                    },
                    modifier = Modifier.size(21.dp),
                )
            }
        }
    }
}

@Composable
private fun SideOnOneLine(side: Side?) {
    if (side == null) return
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        TvCrest(side.crestUrl, size = 22.dp)
        Text(
            text = side.name,
            style = TvTeamName,
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
fun TvChannelPill(channel: ChannelChip) {
    Text(
        text = channel.name,
        color = if (channel.openable) {
            MaterialTheme.colorScheme.onSecondary
        } else {
            Color(Palette.ON_BACKGROUND_MUTED)
        },
        fontSize = 10.5.sp,
        fontWeight = if (channel.openable) FontWeight.Bold else FontWeight.Normal,
        fontStyle = if (channel.openable) FontStyle.Normal else FontStyle.Italic,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = Modifier
            .widthIn(max = 130.dp)
            .clip(RoundedCornerShape(50))
            .then(
                if (channel.openable) {
                    Modifier.background(MaterialTheme.colorScheme.secondary)
                } else {
                    Modifier.border(1.dp, Color(Palette.MUTED_OUTLINE), RoundedCornerShape(50))
                },
            )
            .padding(horizontal = 9.dp, vertical = 4.dp),
    )
}

@Composable
fun TvCrest(url: String?, size: Dp, rounded: Dp = size / 2) {
    val shape = RoundedCornerShape(rounded)
    if (url == null) {
        Box(Modifier.size(size).clip(shape).background(Color(Palette.CARD_BORDER)))
        return
    }
    AsyncImage(
        model = url,
        contentDescription = null,
        contentScale = ContentScale.Fit,
        modifier = Modifier.size(size).clip(shape),
    )
}

private val ROW_HEIGHT = 72.dp
private val RADIUS = 14.dp
private val FAVOURITE_EDGE = 3.dp
