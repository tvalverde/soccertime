package es.mojon.soccertime.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.tv.material3.Icon
import androidx.tv.material3.MaterialTheme
import es.mojon.soccertime.core.ui.Palette
import es.mojon.soccertime.core.ui.SoccertimeIcons

/**
 * The navigation rail, which is where LEFT from the list goes.
 *
 * Icons only. A television has no room to spend on a permanent sidebar of labels, and the two
 * destinations here are a star and a calendar — both of which say what they are.
 */
@Composable
fun TvRail(
    selected: TvDestination,
    onSelect: (TvDestination) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier.width(62.dp).fillMaxHeight(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(Modifier.size(54.dp), contentAlignment = Alignment.Center) {
            Icon(
                imageVector = SoccertimeIcons.CalendarCheck,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(28.dp),
            )
        }

        TvDestination.entries.forEach { destination ->
            RailItem(
                icon = destination.icon,
                selected = destination == selected,
                onClick = { onSelect(destination) },
            )
        }
    }
}

/**
 * Selected and focused are drawn with different resources on purpose.
 *
 * They used to share a `when`, with `selected` resolved first — so arriving at the icon of the
 * screen you were already on changed nothing at all, and the cursor appeared to disappear.
 * They are orthogonal: the neon fill says which screen this is, the halo says where the remote
 * is, and on the one that is both a keyline in the background colour keeps them apart.
 */
@Composable
private fun RailItem(icon: ImageVector, selected: Boolean, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    val interaction = remember { MutableInteractionSource() }

    Box(
        Modifier
            .size(54.dp)
            .onFocusChanged { focused = it.isFocused }
            // No `focusable()` beside this. `clickable` is already a focus target, and
            // adding another puts the focus on the outer one while the inner one is what
            // handles OK — which is a control the remote can highlight and never activate.
            .clickable(interactionSource = interaction, indication = null, onClick = onClick)
            .cursorHalo(focused, radius = RADIUS, onFilledSurface = selected)
            .clip(RoundedCornerShape(RADIUS))
            .then(
                when {
                    selected -> Modifier.background(MaterialTheme.colorScheme.primary)
                    focused -> Modifier.background(Color(Palette.CARD_BORDER))
                    else -> Modifier
                },
            )
            .then(
                if (focused) {
                    Modifier.border(
                        width = 2.dp,
                        color = if (selected) {
                            MaterialTheme.colorScheme.background
                        } else {
                            MaterialTheme.colorScheme.primary
                        },
                        shape = RoundedCornerShape(RADIUS),
                    )
                } else {
                    Modifier
                },
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = when {
                selected -> MaterialTheme.colorScheme.onPrimary
                // Brightened under the cursor. Leaving it muted was the other half of why
                // arriving here read as nothing having happened.
                focused -> MaterialTheme.colorScheme.onBackground
                else -> Color(Palette.ON_BACKGROUND_MUTED)
            },
            modifier = Modifier.size(24.dp),
        )
    }
}

/**
 * The icon is not a property of the destination: it is a resource, and resolving one happens
 * inside composition. Holding it here would have meant loading it before there was a context
 * to load it from.
 */
enum class TvDestination { Favorites, Agenda }

private val TvDestination.icon: ImageVector
    @Composable get() = when (this) {
        TvDestination.Favorites -> SoccertimeIcons.Star
        TvDestination.Agenda -> SoccertimeIcons.Calendar
    }

private val RADIUS = 14.dp
