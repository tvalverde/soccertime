package es.mojon.soccertime.core.playback

import es.mojon.soccertime.core.model.LinkDto

/**
 * Opening a link.
 *
 * **This app requires no particular player and names none.** It hands the URL to the system
 * exactly as the API returned it and lets the system decide who answers: one handler opens
 * it, several with no default raise Android's own chooser — which is navigable with a remote
 * on Fire OS — and a default the reader has set is honoured. There is no `Intent.createChooser`
 * wrapper, because that would ignore that default and add a step to every play on a remote;
 * there is no `<queries>` block and no installation check, because knowing what is installed
 * is not needed to try, and asking would make the app behave differently across Android
 * versions for no gain.
 *
 * The one thing worth handling is nobody answering at all, and that is a dialogue offering to
 * copy or share the link — never a recommendation to install something.
 */
class Playback(private val launcher: IntentLauncher) {

    fun open(link: LinkDto): PlayResult {
        val url = link.link
        if (!link.isOpenable || url.isNullOrBlank()) return PlayResult.Withheld
        return try {
            launcher.launch(url)
            PlayResult.Launched(url)
        } catch (e: NoHandlerException) {
            PlayResult.NoHandler(scheme = link.scheme.ifBlank { url.substringBefore(':') }, link = url)
        }
    }
}

/**
 * Whatever actually starts an activity. An interface so the decision above can be tested
 * without an Android runtime, and so `:core` holds no `Context`.
 */
fun interface IntentLauncher {
    /** @throws NoHandlerException when nothing on the device answers the URL's scheme. */
    fun launch(url: String)
}

/** Raised in place of Android's `ActivityNotFoundException`, which `:core` does not import. */
class NoHandlerException(cause: Throwable? = null) : RuntimeException(cause)

sealed interface PlayResult {
    data class Launched(val link: String) : PlayResult

    /** Nothing on this device opens links of this scheme. */
    data class NoHandler(val scheme: String, val link: String) : PlayResult

    /**
     * The API refused to publish the URL because its scheme is not on the allowlist, so there
     * is nothing to open. Never rendered as a button in the first place; this is the guard
     * for the case where one is rendered anyway.
     */
    data object Withheld : PlayResult
}
