package es.mojon.soccertime.tv.ui.theme

import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.darkColorScheme
import es.mojon.soccertime.core.ui.Fonts
import es.mojon.soccertime.core.ui.Palette

/**
 * The same palette as the phone, in the television's own Material.
 *
 * `androidx.tv.material3` is a separate Material from `androidx.compose.material3`: its
 * components take focus with a remote rather than a pointer, and mixing the two is what
 * produces a screen where half the controls cannot be reached. This module depends on the
 * television's alone.
 */
private val Scheme = darkColorScheme(
    primary = Color(Palette.PRIMARY),
    onPrimary = Color(Palette.ON_PRIMARY),
    secondary = Color(Palette.SECONDARY),
    onSecondary = Color(Palette.ON_SECONDARY),
    tertiary = Color(Palette.FAVOURITE),
    onTertiary = Color(Palette.ON_PRIMARY),
    background = Color(Palette.BACKGROUND),
    onBackground = Color(Palette.ON_BACKGROUND),
    surface = Color(Palette.SURFACE),
    onSurface = Color(Palette.ON_BACKGROUND),
    surfaceVariant = Color(Palette.HAIRLINE),
    onSurfaceVariant = Color(Palette.ON_BACKGROUND_VARIANT),
    border = Color(Palette.OUTLINE),
    borderVariant = Color(Palette.MUTED_OUTLINE),
    error = Color(Palette.DANGER),
    onError = Color(Palette.ON_PRIMARY),
    scrim = Color(Palette.SCRIM),
)

/**
 * Sizes are in dp on a 960×540 canvas, which is what 1920×1080 comes to at the density a Fire
 * TV reports. They are larger than the phone's for the reason every television size is: this
 * is read from a sofa, not from a hand.
 */
val TvScreenTitle = TextStyle(
    fontFamily = Fonts.Display,
    fontWeight = FontWeight.ExtraBold,
    fontSize = 30.sp,
    letterSpacing = (-0.3).sp,
)

val TvEventTime = TextStyle(
    fontFamily = Fonts.Display,
    fontWeight = FontWeight.Bold,
    fontSize = 23.sp,
)

val TvTeamName = TextStyle(
    fontFamily = Fonts.Body,
    fontWeight = FontWeight.SemiBold,
    fontSize = 17.sp,
)

val TvMeta = TextStyle(fontFamily = Fonts.Body, fontSize = 11.5.sp)

val TvHeading = TextStyle(
    fontFamily = Fonts.Body,
    fontWeight = FontWeight.Bold,
    fontSize = 12.sp,
    letterSpacing = 1.6.sp,
)

val TvLabel = TextStyle(fontFamily = Fonts.Body, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)

/**
 * The margin a television crops. Anything drawn outside it may simply not be on the screen,
 * which is why every screen here starts with it rather than with zero.
 */
val OverscanHorizontal = 48.dp
val OverscanVertical = 27.dp

@Composable
fun SoccertimeTvTheme(content: @Composable () -> Unit) =
    MaterialTheme(colorScheme = Scheme, content = content)
