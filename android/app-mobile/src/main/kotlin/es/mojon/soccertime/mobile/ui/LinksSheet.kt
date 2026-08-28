package es.mojon.soccertime.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import es.mojon.soccertime.core.model.LinkDto
import es.mojon.soccertime.core.ui.ChannelLinks
import es.mojon.soccertime.core.ui.EventLinks
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.mobile.R
import es.mojon.soccertime.mobile.ui.theme.DayHeadingStyle

/**
 * The links of one event.
 *
 * One button on the card opens this rather than the card carrying a row of twenty play icons,
 * which is what the website does and what a phone has no room for. Grouped by channel and then
 * by quality, and numbered inside each group, because the links are alternative sources for
 * the same stream and the real gesture is "that one did not start, try the next".
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LinksSheet(
    links: EventLinks,
    onOpen: (LinkDto) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = MaterialTheme.colorScheme.surface,
        scrimColor = Color(Palette.SCRIM).copy(alpha = 0.72f),
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)
                .padding(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Header(links)
            links.channels.forEach { ChannelBlock(it, onOpen) }
            if (links.silent.isNotEmpty()) SilentChannels(links.silent)
        }
    }
}

@Composable
private fun Header(links: EventLinks) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            links.home?.let { Crest(it.crestUrl, size = 22.dp) }
            Text(
                text = links.title,
                color = MaterialTheme.colorScheme.onSurface,
                fontSize = 15.5.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            links.away?.let { Crest(it.crestUrl, size = 22.dp) }
        }
        Row(
            horizontalArrangement = Arrangement.spacedBy(7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (links.live) {
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
            Text(
                text = "${links.time} · ${links.competition}",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 11.5.sp,
            )
        }
    }
}

@Composable
private fun ChannelBlock(channel: ChannelLinks, onOpen: (LinkDto) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            Text(
                text = channel.name,
                color = MaterialTheme.colorScheme.onSecondary,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier
                    .weight(1f, fill = false)
                    .clip(RoundedCornerShape(50))
                    .background(MaterialTheme.colorScheme.secondary)
                    .padding(horizontal = 9.dp, vertical = 3.dp),
            )
            Text(
                text = pluralStringResource(R.plurals.link_count, channel.total, channel.total),
                color = Color(Palette.ON_BACKGROUND_FAINT),
                fontSize = 10.5.sp,
            )
        }

        channel.qualities.forEach { group ->
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    text = if (group.quality == LinkDto.ANY_QUALITY) {
                        stringResource(R.string.quality_unspecified)
                    } else {
                        group.quality
                    },
                    style = DayHeadingStyle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                FlowRow(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    group.links.forEachIndexed { index, link ->
                        LinkTile(number = index + 1, best = index == 0, onOpen = { onOpen(link) })
                    }
                }
            }
        }
    }
}

/**
 * Numbered by position within its quality, which is what makes "the third one worked"
 * something the reader can remember and repeat next week.
 */
@Composable
private fun LinkTile(number: Int, best: Boolean, onOpen: () -> Unit) {
    Box(
        Modifier
            .width(44.dp)
            .height(38.dp)
            .clip(RoundedCornerShape(10.dp))
            .then(
                if (best) {
                    Modifier.background(MaterialTheme.colorScheme.primary)
                } else {
                    Modifier
                        .background(Color(Palette.CARD_BORDER))
                        .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(10.dp))
                },
            )
            .clickable(onClick = onOpen),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "$number",
            color = if (best) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
            fontSize = 13.sp,
            fontWeight = if (best) FontWeight.Bold else FontWeight.SemiBold,
        )
    }
}

@Composable
private fun SilentChannels(names: List<String>) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = stringResource(R.string.also_on),
            style = DayHeadingStyle,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            names.forEach {
                Text(
                    text = it,
                    color = Color(Palette.ON_BACKGROUND_MUTED),
                    fontSize = 11.sp,
                    modifier = Modifier
                        .clip(RoundedCornerShape(50))
                        .border(1.dp, Color(Palette.MUTED_OUTLINE), RoundedCornerShape(50))
                        .padding(horizontal = 10.dp, vertical = 4.dp),
                )
            }
        }
    }
}

/**
 * When nothing on the device answers.
 *
 * It names no application and offers no download. What the reader has is a link, and where
 * they take it is theirs to decide — so the two ways out are copying it and sharing it.
 */
@Composable
fun NoHandlerDialog(
    scheme: String,
    link: String,
    onCopy: () -> Unit,
    onShare: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Text(
                text = stringResource(R.string.no_handler_title),
                style = MaterialTheme.typography.titleLarge,
                fontSize = 19.sp,
                color = MaterialTheme.colorScheme.onSurface,
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text(
                    text = stringResource(R.string.no_handler_body, "$scheme://"),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 13.5.sp,
                    lineHeight = 20.sp,
                )
                Text(
                    text = link,
                    color = Color(Palette.ON_BACKGROUND_MUTED),
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    lineHeight = 16.sp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(10.dp))
                        .background(MaterialTheme.colorScheme.background)
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onCopy) {
                Text(stringResource(R.string.copy_link), color = MaterialTheme.colorScheme.primary)
            }
        },
        dismissButton = {
            Row {
                TextButton(onClick = onShare) {
                    Text(
                        text = stringResource(R.string.share_link),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                TextButton(onClick = onDismiss) {
                    Text(
                        text = stringResource(R.string.close),
                        color = Color(Palette.ON_BACKGROUND_MUTED),
                    )
                }
            }
        },
    )
}
