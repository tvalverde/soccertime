package es.mojon.soccertime.core.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.vectorResource
import es.mojon.soccertime.core.R

/**
 * The icons, which are the Bootstrap Icons the website already uses — the paths come from its
 * own templates, so the two products draw the same star and the same play triangle.
 *
 * Declared as vector drawables under `res/drawable` rather than built in Kotlin from path
 * strings. That is not a style preference: building them here meant parsing SVG path data at
 * runtime, and Compose's parser drew the outline calendar with its right edge missing and its
 * bottom corner curling inward on a Fire TV. The same path rendered correctly everywhere
 * else, so nothing but the device said so. As resources they are compiled and validated by
 * `aapt` at build time and drawn by the platform's own vector pipeline.
 *
 * Compose's `material-icons-core` was the other option and is the wrong one: it is frozen at
 * 1.7.8, so taking it would pin one Compose artifact years behind the BOM that manages every
 * other.
 */
object SoccertimeIcons {

    /** The brand mark, and the glyph on the launcher icon. Never the agenda's. */
    val CalendarCheck: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_calendar_check)

    /** The agenda. A plain calendar, distinct from the brand mark above it in the rail. */
    val Calendar: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_calendar)

    val Play: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_play)

    val Star: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_star)

    val StarOutline: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_star_outline)

    val Search: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_search)

    val Close: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_close)

    val Refresh: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_refresh)

    val Back: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_back)

    val Add: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_add)

    val Warning: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_warning)

    val Bolt: ImageVector @Composable get() =
        ImageVector.vectorResource(R.drawable.ic_bolt)
}
