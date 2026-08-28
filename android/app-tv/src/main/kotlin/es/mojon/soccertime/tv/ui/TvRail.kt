package es.mojon.soccertime.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
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
 * destinations here are a star and a calendar — both of which say what they are. The item
 * under focus takes the neon fill, so pressing LEFT is visibly answered before anything is
 * chosen.
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
                imageVector = SoccertimeIcons.Calendar,
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

@Composable
private fun RailItem(icon: ImageVector, selected: Boolean, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    val interaction = remember { MutableInteractionSource() }

    Box(
        Modifier
            .size(54.dp)
            .onFocusChanged { focused = it.isFocused }
            .focusable(interactionSource = interaction)
            .clickable(interactionSource = interaction, indication = null, onClick = onClick)
            .clip(RoundedCornerShape(14.dp))
            .then(
                when {
                    selected -> Modifier.background(MaterialTheme.colorScheme.primary)
                    focused -> Modifier
                        .background(Color(Palette.CARD_BORDER))
                        .border(2.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(14.dp))
                    else -> Modifier
                },
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = if (selected) {
                MaterialTheme.colorScheme.onPrimary
            } else {
                Color(Palette.ON_BACKGROUND_MUTED)
            },
            modifier = Modifier.size(24.dp),
        )
    }
}

enum class TvDestination(val icon: ImageVector) {
    Favorites(SoccertimeIcons.Star),
    Agenda(SoccertimeIcons.Calendar),
}
