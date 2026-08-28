package es.mojon.soccertime.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import es.mojon.soccertime.core.model.LinkDto
import es.mojon.soccertime.core.ui.ChannelLinks
import es.mojon.soccertime.core.ui.EventLinks
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.tv.R
import es.mojon.soccertime.tv.ui.theme.TvHeading
import es.mojon.soccertime.tv.ui.theme.TvLabel
import es.mojon.soccertime.tv.ui.theme.TvMeta
import es.mojon.soccertime.tv.ui.theme.TvTeamName

/**
 * The links of one event, as master and detail.
 *
 * The phone stacks the channels and scrolls; a remote cannot scroll a long page cheaply, so
 * here the channels are a column on the left and the chosen one's links fill the right. Two
 * presses reach any link instead of twenty — which is the whole reason this is not the phone's
 * sheet with bigger text.
 *
 * Channels carrying nothing are listed under the others and are not focusable. They are the
 * one fact a television agenda exists to give, and they are not somewhere the remote should
 * have to travel through.
 */
@Composable
fun TvLinksPanel(
    links: EventLinks,
    onOpen: (LinkDto) -> Unit,
    modifier: Modifier = Modifier,
) {
    var chosen by remember { mutableIntStateOf(0) }
    val firstLink = remember { FocusRequester() }
    val channel = links.channels.getOrNull(chosen)

    // Opening the panel has to put the remote somewhere, and the first link of the best
    // quality is where the reader was going.
    LaunchedEffect(links.title) { runCatching { firstLink.requestFocus() } }

    Box(
        modifier
            .fillMaxSize()
            .background(Color(Palette.SCRIM)),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            Modifier
                .width(760.dp)
                .height(446.dp)
                .clip(RoundedCornerShape(20.dp))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, MaterialTheme.colorScheme.border, RoundedCornerShape(20.dp)),
        ) {
            Header(links)

            Row(Modifier.fillMaxSize()) {
                Column(
                    Modifier
                        .width(262.dp)
                        .fillMaxHeight()
                        .padding(vertical = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(3.dp),
                ) {
                    Text(
                        text = stringResource(R.string.channels),
                        style = TvHeading,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(start = 20.dp, bottom = 8.dp),
                    )
                    links.channels.forEachIndexed { index, it ->
                        ChannelItem(it, selected = index == chosen) { chosen = index }
                    }
                    if (links.silent.isNotEmpty()) SilentChannels(links.silent)
                }

                Box(Modifier.width(1.dp).fillMaxHeight().background(Color(Palette.HAIRLINE)))

                Column(
                    Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 24.dp, vertical = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    channel?.qualities?.forEachIndexed { groupIndex, group ->
                        Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
                            Text(
                                text = if (group.quality == LinkDto.ANY_QUALITY) {
                                    stringResource(R.string.quality_unspecified)
                                } else {
                                    group.quality
                                },
                                style = TvHeading,
                                fontSize = 10.5.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            FlowRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                group.links.forEachIndexed { index, link ->
                                    LinkTile(
                                        number = index + 1,
                                        onOpen = { onOpen(link) },
                                        focusRequester = if (groupIndex == 0 && index == 0) firstLink else null,
                                    )
                                }
                            }
                        }
                    }

                    Box(Modifier.weight(1f))
                    Text(
                        text = stringResource(R.string.try_the_next_one),
                        style = TvMeta,
                        color = Color(Palette.ON_BACKGROUND_FAINT),
                    )
                }
            }
        }
    }
}

@Composable
private fun Header(links: EventLinks) {
    Row(
        Modifier
            .fillMaxWidth()
            .height(74.dp)
            .padding(horizontal = 26.dp),
        horizontalArrangement = Arrangement.spacedBy(11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        links.home?.let { TvCrest(it.crestUrl, size = 26.dp) }
        Text(
            text = links.title,
            style = TvTeamName,
            fontSize = 19.sp,
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
        links.away?.let { TvCrest(it.crestUrl, size = 26.dp) }
        if (links.live) {
            Text(
                text = stringResource(R.string.live),
                color = MaterialTheme.colorScheme.onPrimary,
                fontSize = 9.5.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.5.sp,
                modifier = Modifier
                    .clip(RoundedCornerShape(50))
                    .background(MaterialTheme.colorScheme.primary)
                    .padding(horizontal = 8.dp, vertical = 3.dp),
            )
        }
        Text(
            text = "${links.time} · ${links.competition}",
            style = TvMeta,
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun ChannelItem(channel: ChannelLinks, selected: Boolean, onSelect: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    val interaction = remember { MutableInteractionSource() }

    Row(
        Modifier
            .fillMaxWidth()
            .height(46.dp)
            .onFocusChanged {
                focused = it.isFocused
                if (it.isFocused) onSelect()
            }
            .focusable(interactionSource = interaction)
            .clickable(interactionSource = interaction, indication = null, onClick = onSelect)
            .background(if (selected || focused) Color(Palette.CARD_BORDER) else Color.Transparent)
            .padding(start = 17.dp, end = 20.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .width(3.dp)
                .height(46.dp)
                .background(
                    if (selected) MaterialTheme.colorScheme.primary else Color.Transparent,
                ),
        )
        Column(Modifier.padding(start = 14.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                text = channel.name,
                style = TvLabel,
                fontSize = 13.5.sp,
                color = MaterialTheme.colorScheme.secondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = pluralStringResource(R.plurals.link_count, channel.total, channel.total),
                style = TvMeta,
                fontSize = 10.5.sp,
                color = Color(Palette.ON_BACKGROUND_MUTED),
            )
        }
    }
}

@Composable
private fun SilentChannels(names: List<String>) {
    Column(
        Modifier.padding(start = 20.dp, end = 20.dp, top = 6.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        names.forEach {
            Text(
                text = it,
                style = TvMeta,
                fontSize = 12.5.sp,
                fontStyle = FontStyle.Italic,
                color = Color(Palette.ON_BACKGROUND_MUTED),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Text(
            text = stringResource(R.string.no_link_explained),
            style = TvMeta,
            fontSize = 10.5.sp,
            color = Color(Palette.ON_BACKGROUND_FAINT),
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}

@Composable
private fun LinkTile(number: Int, onOpen: () -> Unit, focusRequester: FocusRequester?) {
    var focused by remember { mutableStateOf(false) }
    val interaction = remember { MutableInteractionSource() }

    Box(
        Modifier
            .size(width = 60.dp, height = 46.dp)
            .then(focusRequester?.let { Modifier.focusRequester(it) } ?: Modifier)
            .onFocusChanged { focused = it.isFocused }
            .focusable(interactionSource = interaction)
            .clickable(interactionSource = interaction, indication = null, onClick = onOpen)
            .clip(RoundedCornerShape(11.dp))
            .then(
                if (focused) {
                    Modifier.background(MaterialTheme.colorScheme.primary)
                } else {
                    Modifier
                        .background(Color(Palette.CARD_BORDER))
                        .border(1.dp, MaterialTheme.colorScheme.border, RoundedCornerShape(11.dp))
                },
            ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "$number",
            style = TvLabel,
            fontSize = 16.sp,
            color = if (focused) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
        )
    }
}

/**
 * Nothing on the device answered. It names no application and offers no download — a
 * television has no clipboard worth using and nowhere to share to, so what it can honestly do
 * is say which scheme went unanswered and show the link.
 */
@Composable
fun TvNoHandler(scheme: String, link: String, modifier: Modifier = Modifier) {
    Box(
        modifier.fillMaxSize().background(Color(Palette.SCRIM)),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            Modifier
                .width(600.dp)
                .clip(RoundedCornerShape(18.dp))
                .background(MaterialTheme.colorScheme.surface)
                .border(1.dp, MaterialTheme.colorScheme.border, RoundedCornerShape(18.dp))
                .padding(26.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(
                text = stringResource(R.string.no_handler_title),
                style = TvTeamName,
                fontSize = 21.sp,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                text = stringResource(R.string.no_handler_body_tv, "$scheme://"),
                style = TvLabel,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = link,
                style = TvMeta,
                fontSize = 12.sp,
                color = Color(Palette.ON_BACKGROUND_MUTED),
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(MaterialTheme.colorScheme.background)
                    .padding(horizontal = 14.dp, vertical = 11.dp),
            )
            Text(
                text = stringResource(R.string.back_to_return),
                style = TvMeta,
                color = Color(Palette.ON_BACKGROUND_FAINT),
            )
        }
    }
}
