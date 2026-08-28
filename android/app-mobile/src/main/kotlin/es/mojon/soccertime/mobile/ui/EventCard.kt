package es.mojon.soccertime.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import es.mojon.soccertime.core.ui.ChannelChip
import es.mojon.soccertime.core.ui.EventUi
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons
import es.mojon.soccertime.core.ui.Side
import es.mojon.soccertime.mobile.R
import es.mojon.soccertime.mobile.ui.theme.EventTimeStyle

/**
 * One event.
 *
 * The only component the agenda and the favourites screen share, and the one the design gate
 * settled. The two sides are stacked rather than set on one line: "FC Barcelona Femenino —
 * Costa Adeje Tenerife" does not fit across a phone, and a layout that truncates the away team
 * on the longest fixtures fails exactly where it is most needed.
 */
@Composable
fun EventCard(
    event: EventUi,
    onPlay: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val gold = MaterialTheme.colorScheme.tertiary
    Row(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(CARD_RADIUS))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, Color(Palette.CARD_BORDER), RoundedCornerShape(CARD_RADIUS))
            // The gold edge marks what the reader follows. Drawn behind the card rather than
            // as a leading box so it is clipped by the same rounded corner, which is what the
            // site's `border-left` does.
            .then(
                if (event.favorite) {
                    Modifier.drawBehind {
                        drawRect(color = gold, size = Size(FAVOURITE_EDGE.toPx(), size.height))
                    }
                } else {
                    Modifier
                },
            )
            .padding(start = 12.dp, top = 11.dp, end = 12.dp, bottom = 11.dp),
        horizontalArrangement = Arrangement.spacedBy(11.dp),
    ) {
        TimeColumn(event)

        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            CompetitionLine(event)
            if (event.title != null) SingleTitle(event) else Sides(event)
            if (event.channels.isNotEmpty()) Channels(event)
        }

        if (event.openable) {
            PlayButton(onPlay, Modifier.align(Alignment.CenterVertically))
        }
    }
}

/**
 * The time, and whether it is on now.
 *
 * The width is fixed rather than left to the content, because a fixed one is what keeps every
 * hour on the list aligned down the left edge — which is how an agenda is read at a glance,
 * and what a column sized to its content would give up, zigzagging by whether a row carried a
 * badge.
 *
 * It is [TIME_COLUMN] wide because that is what the two things living in it ask for: `00:00`
 * at the time's 20sp, and `DIRECTO` at the badge's 8.5sp, with slack. At 48dp it was a
 * point too narrow for either — `21:30` measures about 49 — so the hour wrapped to `21:3 / 0`
 * on every screen, and the badge, squeezed into a nearly square box with a 50% corner radius,
 * became a green disc. One measurement, two symptoms.
 */
@Composable
private fun TimeColumn(event: EventUi) {
    Column(Modifier.width(TIME_COLUMN), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(
            text = event.time,
            style = EventTimeStyle,
            color = if (event.live) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
            // Belt and braces beside the width: an hour is five glyphs and never two lines,
            // whatever a future type ramp or a reader's font scale does to it.
            maxLines = 1,
            softWrap = false,
        )
        if (event.live) LiveBadge()
    }
}

@Composable
private fun LiveBadge() {
    Text(
        text = stringResource(R.string.live),
        color = MaterialTheme.colorScheme.onPrimary,
        fontSize = 8.5.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = 0.5.sp,
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(MaterialTheme.colorScheme.primary)
            .padding(horizontal = 6.dp, vertical = 2.dp),
    )
}

@Composable
private fun CompetitionLine(event: EventUi) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Crest(event.flagUrl, size = 14.dp, rounded = 2.dp)
        Text(
            text = event.competition,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 11.sp,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f, fill = false),
        )
        Text(
            text = event.sport,
            color = Color(Palette.ON_BACKGROUND_FAINT),
            fontSize = 9.5.sp,
            letterSpacing = 0.6.sp,
            maxLines = 1,
        )
    }
}

@Composable
private fun SingleTitle(event: EventUi) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = event.title.orEmpty(),
            color = MaterialTheme.colorScheme.onSurface,
            fontSize = 14.5.sp,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f, fill = false),
        )
        event.details?.let {
            Text(it, color = Color(Palette.ON_BACKGROUND_FAINT), fontSize = 10.5.sp, maxLines = 1)
        }
    }
}

@Composable
private fun Sides(event: EventUi) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        event.home?.let { SideRow(it) }
        event.away?.let { SideRow(it) }
    }
}

@Composable
private fun SideRow(side: Side) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Crest(side.crestUrl, size = 20.dp)
        Text(
            text = side.name,
            color = MaterialTheme.colorScheme.onSurface,
            fontSize = 14.5.sp,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun Channels(event: EventUi) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        event.channels.forEach { ChannelPill(it, Modifier.weight(1f, fill = false)) }
        if (event.hiddenChannels > 0) {
            Text(
                text = "+${event.hiddenChannels}",
                color = Color(Palette.ON_BACKGROUND_MUTED),
                fontSize = 10.sp,
            )
        }
    }
}

/**
 * A channel with nothing to open is drawn muted and italic rather than dropped. It carries the
 * one fact a television agenda exists to give — where the match is on — and the site once hid
 * it for 1,809 of 2,148 future events before learning that.
 */
@Composable
fun ChannelPill(channel: ChannelChip, modifier: Modifier = Modifier) {
    Text(
        text = channel.name,
        color = if (channel.openable) {
            MaterialTheme.colorScheme.onSecondary
        } else {
            Color(Palette.ON_BACKGROUND_MUTED)
        },
        fontSize = 10.sp,
        fontWeight = if (channel.openable) FontWeight.Bold else FontWeight.Normal,
        fontStyle = if (channel.openable) FontStyle.Normal else FontStyle.Italic,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = modifier
            .clip(RoundedCornerShape(50))
            .then(
                if (channel.openable) {
                    Modifier.background(MaterialTheme.colorScheme.secondary)
                } else {
                    Modifier.border(1.dp, Color(Palette.MUTED_OUTLINE), RoundedCornerShape(50))
                },
            )
            .padding(horizontal = 8.dp, vertical = 3.dp),
    )
}

@Composable
private fun PlayButton(onPlay: () -> Unit, modifier: Modifier = Modifier) {
    Box(
        modifier
            .size(42.dp)
            .clip(RoundedCornerShape(50))
            .background(MaterialTheme.colorScheme.primary)
            .clickable(onClick = onPlay),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = SoccertimeIcons.Play,
            contentDescription = stringResource(R.string.play),
            tint = MaterialTheme.colorScheme.onPrimary,
            modifier = Modifier.size(24.dp),
        )
    }
}

/**
 * A crest the API never sent, or one whose file is gone, is a normal state rather than a
 * failure — the media directory has lost files before. The placeholder keeps the row's shape
 * so a list of them does not jitter.
 */
@Composable
fun Crest(url: String?, size: Dp, rounded: Dp = size / 2) {
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

/** What `00:00` at 20sp and `DIRECTO` at 8.5sp both fit inside, with room to spare. */
private val TIME_COLUMN = 62.dp

private val CARD_RADIUS = 14.dp
private val FAVOURITE_EDGE = 3.dp
