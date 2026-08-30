package es.mojon.soccertime.core.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * The favourites as a file the reader can carry between installations.
 *
 * A debug build cannot install over a release — the signatures differ — so every switch
 * uninstalls, and an uninstall takes the favourites with it. This file is what survives:
 * export before, import after, and the choice outlives the signature.
 *
 * [decode] requires the `version` field. Every field of the envelope has a default otherwise,
 * so without that requirement *any* JSON object would decode as an empty, "successful" import
 * — a shopping list would report itself imported. A version this build does not know is still
 * read: unknown fields are ignored, and adding only what it can name is the harmless half of
 * any future shape.
 */
object FavoritesTransfer {

    const val SUGGESTED_FILE_NAME = "soccertime-favoritos.json"

    fun encode(following: Following): String =
        JSON.encodeToString(
            Envelope(version = VERSION, teams = following.teams, competitions = following.competitions),
        )

    /** Null for anything that is not an export of ours. */
    fun decode(text: String): Following? =
        runCatching { JSON.decodeFromString<Envelope>(text) }.getOrNull()
            ?.let { Following(teams = it.teams, competitions = it.competitions) }

    @Serializable
    private data class Envelope(
        val version: Int,
        val teams: List<FollowedItem> = emptyList(),
        val competitions: List<FollowedItem> = emptyList(),
    )

    private const val VERSION = 1
    private val JSON = Json {
        ignoreUnknownKeys = true
        prettyPrint = true
    }
}
