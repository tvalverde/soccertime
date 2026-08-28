package es.mojon.soccertime.core.playback

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import androidx.core.content.getSystemService
import androidx.core.net.toUri

/**
 * Hands a link to the system and gets out of the way.
 *
 * `ACTION_VIEW` with the URL exactly as the API sent it, and nothing else: whoever answers,
 * answers. One handler opens it, several with no default raise Android's own chooser — which
 * is navigable with a remote on Fire OS — and a default the reader has set is honoured.
 * `NEW_TASK` so the player appears as its own task rather than inside this one, which is what
 * makes Back return here instead of unwinding through the stream.
 */
class SystemIntentLauncher(private val context: Context) : IntentLauncher {

    override fun launch(url: String) {
        val intent = Intent(Intent.ACTION_VIEW, url.toUri())
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            context.startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            throw NoHandlerException(e)
        }
    }
}

/**
 * The two ways out when nothing on the device answers. Neither names an app to install: what
 * the reader wants is the link, and where they take it is theirs to decide.
 */
object LinkSharing {

    fun copy(context: Context, url: String): Boolean {
        val clipboard = context.getSystemService<ClipboardManager>() ?: return false
        clipboard.setPrimaryClip(ClipData.newPlainText(LABEL, url))
        return true
    }

    fun share(context: Context, url: String): Boolean {
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, url)
        }
        return try {
            context.startActivity(
                Intent.createChooser(send, null).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            )
            true
        } catch (e: ActivityNotFoundException) {
            false
        }
    }

    private const val LABEL = "Soccertime"
}
