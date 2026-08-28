package es.mojon.soccertime.core.ui

import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import es.mojon.soccertime.core.R

/**
 * The two faces the website uses, declared once for both applications.
 *
 * Carried as files rather than through Android's downloadable fonts, which are served by
 * Google Play services: a Fire TV has none, so on the one device this project exists for a
 * downloadable font is a silent fallback to the system sans-serif — and silent is the problem.
 *
 * One file per weight, not the variable originals. Variable axes need API 26 and `minSdk`
 * here is 25, so a variable file would render every weight at its default on the television
 * and flatten the whole type hierarchy. Licences are in `android/licenses/`.
 */
object Fonts {

    /** Headings and times. Narrow, and the reason a listing of times reads as a column. */
    val Display = FontFamily(
        Font(R.font.anybody_bold, FontWeight.Bold),
        Font(R.font.anybody_extrabold, FontWeight.ExtraBold),
    )

    val Body = FontFamily(
        Font(R.font.inter_regular, FontWeight.Normal),
        Font(R.font.inter_medium, FontWeight.Medium),
        Font(R.font.inter_semibold, FontWeight.SemiBold),
        Font(R.font.inter_bold, FontWeight.Bold),
    )
}
