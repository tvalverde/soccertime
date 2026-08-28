package es.mojon.soccertime.tv.ui

import androidx.compose.foundation.focusGroup
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.focus.focusProperties
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * The fill says the state. The halo says the cursor.
 *
 * Four bugs on this television had the same shape: a control drew "you are here" and "the
 * cursor is here" with the same resource, so where the two met one swallowed the other and the
 * remote appeared to vanish. It happened on the navigation rail, where the selected icon
 * looked identical focused and unfocused; on the channel column, where `selected || focused`
 * painted one background for both; and it would have happened again on the link tiles the
 * moment an opened one needed marking.
 *
 * So they are separated here, once, for every control on the screen to use. Background and
 * border belong to the state a control is in. Focus is a halo and a tenth of extra size —
 * neither of which any state uses, and both of which read from a sofa.
 */
fun Modifier.cursorHalo(
    focused: Boolean,
    radius: Dp,
    /** Set when the control is already filled, so the halo does not merge into the fill. */
    onFilledSurface: Boolean = false,
    /**
     * Off for anything that already spans the screen.
     *
     * A tile grows into the space around it; a row eight hundred points wide grows forty
     * points past each edge, where the list clips it — brushed edges and an overlap onto the
     * rows above and below. On those the halo carries the whole message, which is why the
     * design only ever draws the growth on tiles and avatars.
     */
    grow: Boolean = true,
    spread: Dp = DEFAULT_SPREAD,
): Modifier = if (!focused) {
    this
} else {
    // Scaled by drawing rather than by layout: growing the box itself would shove every
    // sibling in the column aside by the difference each time the remote moved.
    then(if (grow) Modifier.graphicsLayer { scaleX = FOCUSED_SCALE; scaleY = FOCUSED_SCALE } else Modifier)
        .drawBehind {
            val spreadPx = spread.toPx()
            drawRoundRect(
                color = Color(if (onFilledSurface) HALO_ON_FILL else HALO),
                topLeft = Offset(-spreadPx, -spreadPx),
                size = Size(size.width + spreadPx * 2, size.height + spreadPx * 2),
                cornerRadius = CornerRadius(radius.toPx() + spreadPx),
            )
        }
}

/** A tenth, which is what `tv-material`'s own focused surface grows by. */
const val FOCUSED_SCALE: Float = 1.10f

private val DEFAULT_SPREAD = 5.dp

/** Neon at low opacity: visible against the background, never mistaken for a fill. */
private const val HALO = 0x29_00FF41

/**
 * Stronger, because it sits around a control that is already neon. What separates the two is
 * the keyline the caller draws in the background colour between them.
 */
private const val HALO_ON_FILL = 0x4D_00FF41

/**
 * A region the cursor cannot wander out of except the ways it is given.
 *
 * Nothing sits above the first row of a list or below the last, so a focus search asked to go
 * up settled for whatever was nearest in any direction — from the top of the agenda, the
 * navigation rail, up and to the left. A diagonal jump out of the list and onto a menu, which
 * is not a thing anybody pressed for.
 *
 * It has to be `onExit` and not the plain `up`/`down`/`right` properties. Those are inherited
 * by every focus target below them — which is exactly what makes `right = firstLink` work on
 * the channel column — so setting them here would cancel the cursor's movement *between* the
 * rows as well as out of them, and leave a list nothing could walk. `onExit` runs only when
 * focus is about to cross this group's boundary.
 */
fun Modifier.focusEnclosure(ways: List<FocusDirection>): Modifier =
    focusGroup().focusProperties {
        onExit = { if (requestedFocusDirection !in ways) cancelFocusChange() }
    }

/**
 * What a Fire TV remote sends for its play button.
 *
 * Both, because the hardware is not consistent: some remotes send a dedicated PLAY, most send
 * the PLAY/PAUSE toggle, and a keyboard paired with the box sends the media key. All of them
 * mean one thing on a listing of things to watch — show me where this is on.
 */
val TvPlayKeys: Set<Key> = setOf(Key.MediaPlay, Key.MediaPlayPause)
