package es.mojon.soccertime.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.focusGroup
import androidx.compose.foundation.rememberScrollState
import androidx.compose.ui.focus.focusProperties
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
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onKeyEvent
import androidx.compose.ui.input.key.type
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
 *
 * The route between the two columns is tied by hand rather than left to the focus search.
 * Geometry got the remote there and could not get it back: moving onto a channel selects it,
 * which rebuilds the entire right-hand column underneath the search that was about to look
 * through it. LEFT and RIGHT are named here instead, so neither depends on what happens to be
 * laid out where at the instant a key is pressed.
 */
@Composable
fun TvLinksPanel(
    links: EventLinks,
    /** The one already launched, so the panel can say which it was. Null until one is. */
    opened: LinkDto?,
    onOpen: (LinkDto) -> Unit,
    modifier: Modifier = Modifier,
) {
    var chosen by remember { mutableIntStateOf(0) }
    val firstLink = remember { FocusRequester() }
    val currentChannel = remember { FocusRequester() }
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
                // Nothing leaves this panel by pressing a direction. It is an overlay in the
                // same composition rather than a window, so the rows behind the scrim are
                // still focus targets — DOWN off the end of the channel column would walk the
                // cursor into a list nobody can see. Marking the content behind unfocusable
                // does not reach them: a row's search for that property stops at the focus
                // group its own list puts around it. ATRÁS is the way out, as the map says.
                .focusEnclosure(EveryDirection)
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
                        .padding(vertical = 16.dp)
                        // RIGHT *out of* this column lands on the first link of the best
                        // quality, whichever channel the cursor is on and whatever was rebuilt.
                        // Above the group, so only the group reads it: written below, every
                        // channel would inherit it and RIGHT would stop meaning anything else.
                        .focusProperties { right = firstLink }
                        .focusGroup(),
                    verticalArrangement = Arrangement.spacedBy(3.dp),
                ) {
                    Text(
                        text = stringResource(R.string.channels),
                        style = TvHeading,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(start = 20.dp, bottom = 8.dp),
                    )
                    links.channels.forEachIndexed { index, it ->
                        ChannelItem(
                            channel = it,
                            selected = index == chosen,
                            focusRequester = if (index == chosen) currentChannel else null,
                            onSelect = { chosen = index },
                        )
                    }
                    if (links.silent.isNotEmpty()) SilentChannels(links.silent)
                }

                Box(Modifier.width(1.dp).fillMaxHeight().background(Color(Palette.HAIRLINE)))

                Column(
                    Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 24.dp, vertical = 16.dp)
                        // LEFT *out of* this column goes back to the channel these links
                        // belong to. Inherited by the tiles instead of read by the group, it
                        // sent LEFT from link 3 to the channel rather than to link 2 — every
                        // tile carrying an instruction meant for the column's edge.
                        .focusProperties { left = currentChannel }
                        .focusGroup(),
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
                                        opened = link == opened,
                                        onOpen = { onOpen(link) },
                                        focusRequester = if (groupIndex == 0 && index == 0) firstLink else null,
                                    )
                                }
                            }
                        }
                    }

                    Box(Modifier.weight(1f))
                    // The advice is only worth giving because the panel stays open to take it
                    // — and only when there is a next one. On an event whose channels publish
                    // nothing, "try the next" was an instruction with nothing to obey it with.
                    Text(
                        text = when {
                            !links.hasSomethingToOpen -> stringResource(R.string.nothing_to_open_here)
                            opened == null -> stringResource(R.string.try_the_next_one)
                            else -> stringResource(R.string.opened_try_the_next_one)
                        },
                        style = TvMeta,
                        color = if (opened != null) {
                            MaterialTheme.colorScheme.secondary
                        } else {
                            Color(Palette.ON_BACKGROUND_FAINT)
                        },
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

/**
 * One channel, in up to three states at once.
 *
 * `selected` means these are the links on the right; `focused` means the remote is here. They
 * used to share one background and were therefore indistinguishable — and since arriving at a
 * channel also selects it, the difference only ever shows once the cursor has moved to the
 * links, which is exactly when the reader needs to know whose links they are.
 */
@Composable
private fun ChannelItem(
    channel: ChannelLinks,
    selected: Boolean,
    focusRequester: FocusRequester?,
    onSelect: () -> Unit,
) {
    var focused by remember { mutableStateOf(false) }
    val interaction = remember { MutableInteractionSource() }

    Row(
        Modifier
            .fillMaxWidth()
            .height(46.dp)
            .padding(horizontal = 8.dp)
            .then(focusRequester?.let { Modifier.focusRequester(it) } ?: Modifier)
            .onFocusChanged {
                focused = it.isFocused
                if (it.isFocused) onSelect()
            }
            // No `focusable()` beside this. `clickable` is already a focus target, and
            // adding another puts the focus on the outer one while the inner one is what
            // handles OK — which is a control the remote can highlight and never activate.
            .clickable(interactionSource = interaction, indication = null, onClick = onSelect)
            .cursorHalo(focused, radius = CHANNEL_RADIUS, grow = false)
            .clip(RoundedCornerShape(CHANNEL_RADIUS))
            .background(if (selected) Color(Palette.CARD_BORDER) else Color.Transparent)
            .then(
                if (focused) {
                    Modifier.border(
                        2.dp,
                        MaterialTheme.colorScheme.primary,
                        RoundedCornerShape(CHANNEL_RADIUS),
                    )
                } else {
                    Modifier
                },
            )
            .padding(start = 9.dp, end = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .width(3.dp)
                .height(30.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(
                    if (selected) MaterialTheme.colorScheme.primary else Color.Transparent,
                ),
        )
        Column(Modifier.padding(start = 14.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                text = channel.name,
                style = TvLabel,
                fontSize = 13.5.sp,
                color = if (selected) {
                    MaterialTheme.colorScheme.secondary
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
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

/**
 * One link.
 *
 * Focus was the neon fill here until the panel began staying open, which gave the tile a
 * second thing to say — this is the one you launched — and two fills cannot share a shape.
 * The fill now belongs to that state, in the cyan this app already uses for a channel, and
 * focus is the halo every other control on this screen uses.
 */
@Composable
private fun LinkTile(
    number: Int,
    opened: Boolean,
    onOpen: () -> Unit,
    focusRequester: FocusRequester?,
) {
    var focused by remember { mutableStateOf(false) }
    val interaction = remember { MutableInteractionSource() }

    Box(
        Modifier
            .size(width = 60.dp, height = 46.dp)
            .then(focusRequester?.let { Modifier.focusRequester(it) } ?: Modifier)
            .onFocusChanged { focused = it.isFocused }
            // The same key that opened this panel from the row opens the link inside it.
            .onKeyEvent { key ->
                if (key.type == KeyEventType.KeyDown && key.key in TvPlayKeys) {
                    onOpen()
                    true
                } else {
                    false
                }
            }
            .clickable(interactionSource = interaction, indication = null, onClick = onOpen)
            .cursorHalo(focused, radius = TILE_RADIUS, onFilledSurface = opened)
            .clip(RoundedCornerShape(TILE_RADIUS))
            .background(
                if (opened) {
                    MaterialTheme.colorScheme.secondary
                } else {
                    Color(Palette.CARD_BORDER)
                },
            )
            .border(
                width = if (focused) 2.dp else 1.dp,
                color = when {
                    focused && opened -> MaterialTheme.colorScheme.surface
                    focused -> MaterialTheme.colorScheme.primary
                    opened -> MaterialTheme.colorScheme.secondary
                    else -> MaterialTheme.colorScheme.border
                },
                shape = RoundedCornerShape(TILE_RADIUS),
            ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "$number",
            style = TvLabel,
            fontSize = 16.sp,
            color = if (opened) {
                MaterialTheme.colorScheme.onSecondary
            } else {
                MaterialTheme.colorScheme.onSurface
            },
        )
    }
}

private val CHANNEL_RADIUS = 10.dp
private val TILE_RADIUS = 11.dp

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
