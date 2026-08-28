package es.mojon.soccertime.mobile.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import es.mojon.soccertime.core.ui.Fonts
import es.mojon.soccertime.core.ui.Palette

/**
 * The site's own colours, in Material's slots.
 *
 * There is one scheme and it is dark, whatever the device is set to, and the system setting
 * is deliberately not consulted. The site has no light theme either: it is a listing read on a
 * sofa in the evening, the neon green only reads as "on now" against near-black, and a light
 * variant would be a second design nobody has drawn.
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
    surfaceContainerHighest = Color(Palette.HAIRLINE),
    outline = Color(Palette.OUTLINE),
    outlineVariant = Color(Palette.MUTED_OUTLINE),
    error = Color(Palette.DANGER),
    onError = Color(Palette.ON_PRIMARY),
    scrim = Color(Palette.SCRIM),
)

/**
 * Anybody for anything that is read at a glance — the time on a row, a screen title — and
 * Inter for everything read as words. The same pairing `theme.css` declares.
 */
private val Type = Typography().let { default ->
    default.copy(
        displaySmall = default.displaySmall.copy(fontFamily = Fonts.Display, fontWeight = FontWeight.ExtraBold),
        headlineMedium = default.headlineMedium.copy(fontFamily = Fonts.Display, fontWeight = FontWeight.ExtraBold),
        headlineSmall = default.headlineSmall.copy(fontFamily = Fonts.Display, fontWeight = FontWeight.Bold),
        titleLarge = default.titleLarge.copy(fontFamily = Fonts.Display, fontWeight = FontWeight.Bold),
        titleMedium = default.titleMedium.copy(fontFamily = Fonts.Body, fontWeight = FontWeight.SemiBold),
        titleSmall = default.titleSmall.copy(fontFamily = Fonts.Body, fontWeight = FontWeight.SemiBold),
        bodyLarge = default.bodyLarge.copy(fontFamily = Fonts.Body),
        bodyMedium = default.bodyMedium.copy(fontFamily = Fonts.Body),
        bodySmall = default.bodySmall.copy(fontFamily = Fonts.Body),
        labelLarge = default.labelLarge.copy(fontFamily = Fonts.Body, fontWeight = FontWeight.SemiBold),
        labelMedium = default.labelMedium.copy(fontFamily = Fonts.Body, fontWeight = FontWeight.SemiBold),
        labelSmall = default.labelSmall.copy(fontFamily = Fonts.Body, fontWeight = FontWeight.SemiBold),
    )
}

/** The time on a row: narrow, heavy, and the thing the eye lands on first. */
val EventTimeStyle = TextStyle(
    fontFamily = Fonts.Display,
    fontWeight = FontWeight.Bold,
    fontSize = 20.sp,
    letterSpacing = (-0.01).em,
)

/** A day heading, set in letter-spaced capitals as the design does. */
val DayHeadingStyle = TextStyle(
    fontFamily = Fonts.Body,
    fontWeight = FontWeight.Bold,
    fontSize = 10.5.sp,
    letterSpacing = 1.4.sp,
)

@Composable
fun SoccertimeTheme(content: @Composable () -> Unit) =
    MaterialTheme(colorScheme = Scheme, typography = Type, content = content)
