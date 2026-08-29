package es.mojon.soccertime.core.ui

import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.painter.ColorPainter
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.Dp
import coil3.compose.AsyncImage

/**
 * A crest, a badge or a flag, at the size the row has already reserved for it.
 *
 * Three states are drawn the same on purpose, because the reader can do nothing about any of
 * them: the API sent no image, the file behind the URL is gone, or the request failed. The API
 * serves a URL whether or not the file is behind it — deliberately, since a 404 from the web
 * server beats a 500 from the serializer — and the media directory has lost files before, 49 of
 * them at once. Without `error` and `fallback` Coil draws nothing at all for those, which is a
 * hole in a row whose space is already spoken for rather than a placeholder in it.
 *
 * Loading is left blank. The box has a fixed size, so nothing moves while the image arrives, and
 * a grid of grey squares is a worse first frame than a few crests landing late.
 *
 * It lives here and not in either application because both draw it identically, and a copy each
 * is a copy that gets the next fix and a copy that does not.
 */
@Composable
fun Crest(url: String?, size: Dp, rounded: Dp = size / 2) {
    val missing = ColorPainter(Color(Palette.CARD_BORDER))
    AsyncImage(
        model = url,
        contentDescription = null,
        contentScale = ContentScale.Fit,
        error = missing,
        fallback = missing,
        modifier = Modifier.size(size).clip(RoundedCornerShape(rounded)),
    )
}
