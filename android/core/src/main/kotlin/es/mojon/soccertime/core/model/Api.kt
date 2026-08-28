package es.mojon.soccertime.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * The shapes the API answers with, named as it names them.
 *
 * Every field the app does not read is left out, and the parser is configured to ignore what
 * it does not know: an APK already on a Fire TV cannot be updated in step with the server, so
 * a field added to the API has to be a no-op for it rather than a crash. For the same reason
 * every field that can be absent carries a default — a response that lost one renders an
 * incomplete row instead of failing the whole page.
 */

@Serializable
data class Page<T>(
    val count: Int = 0,
    /**
     * DRF builds this from the request it saw, and behind the proxy that is a path without the
     * `/soccertime` prefix the site is actually served under. It is kept for the one thing it
     * reliably says — whether another page exists — and never followed: the caller asks for
     * `page + 1` instead.
     */
    val next: String? = null,
    val previous: String? = null,
    val results: List<T> = emptyList(),
)

@Serializable
data class ImageDto(
    val url: String,
    val width: Int = 0,
    val height: Int = 0,
)

@Serializable
data class SportDto(
    val id: Int,
    val name: String = "",
    val order: Int = 0,
)

@Serializable
data class FlagDto(
    val id: Int,
    val name: String = "",
    @SerialName("display_name") val displayName: String = "",
    val image: ImageDto? = null,
)

@Serializable
data class CompetitionDto(
    val id: Int,
    val name: String = "",
    val sport: SportDto = SportDto(id = 0),
    val flag: FlagDto? = null,
    @SerialName("is_favorite") val isFavorite: Boolean = false,
    @SerialName("upcoming_event_count") val upcomingEventCount: Int? = null,
)

@Serializable
data class TeamDto(
    val id: Int,
    val name: String = "",
    val crest: ImageDto? = null,
    @SerialName("is_favorite") val isFavorite: Boolean = false,
)

@Serializable
data class LinkDto(
    val id: Int,
    val name: String = "",
    val quality: String = ANY_QUALITY,
    /**
     * Null when the stored URL uses a scheme the site refuses to render. The value itself is
     * the payload there, so it is withheld rather than escaped — and a client that assumed a
     * string would crash on precisely the rows an attacker controls.
     */
    val link: String? = null,
    val scheme: String = "",
    val playable: Boolean = false,
    val enabled: Boolean = false,
) {
    /** The only links worth putting a button on: enabled, allowed, and actually carrying one. */
    val isOpenable: Boolean get() = enabled && playable && !link.isNullOrBlank()

    companion object {
        const val ANY_QUALITY: String = "ANY"
    }
}

@Serializable
data class ChannelDto(
    val id: Int,
    val name: String = "",
    val links: List<LinkDto> = emptyList(),
) {
    val openableLinks: List<LinkDto> get() = links.filter(LinkDto::isOpenable)
}

@Serializable
data class EventDto(
    val id: Int,
    @SerialName("event_type") val eventType: String = "",
    val title: String? = null,
    val name: String? = null,
    /** Null on anything that is not a match: a race and a simple event have no two sides. */
    val local: TeamDto? = null,
    val visitor: TeamDto? = null,
    val competition: CompetitionDto = CompetitionDto(id = 0),
    /** ISO-8601 with the offset the site keeps, e.g. `2026-08-30T17:00:00+02:00`. */
    val date: String = "",
    @SerialName("date_end") val dateEnd: String? = null,
    val details: String? = null,
    val channels: List<ChannelDto> = emptyList(),
    @SerialName("is_favorite") val isFavorite: Boolean = false,
    val watchable: Boolean = false,
) {
    val isMatch: Boolean get() = local != null && visitor != null

    /** Channels that can be opened first, which is the order the site's own listing uses. */
    val channelsByAvailability: List<ChannelDto>
        get() = channels.sortedByDescending { it.openableLinks.isNotEmpty() }
}
