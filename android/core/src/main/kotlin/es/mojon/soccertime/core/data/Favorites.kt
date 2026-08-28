package es.mojon.soccertime.core.data

import es.mojon.soccertime.core.model.EventDto

/**
 * What this device follows, and which events that covers.
 *
 * The rule is `EventQuerySet.for_selection` in `soccertime/models.py`, kept the same on
 * purpose so the app and the site agree about what "my favourites" means: a team counts when
 * it is on **either** side of a match, and a competition counts for **every** event in it,
 * matches included. That last part is where the site's own curated list parts company with a
 * visitor's, and a visitor's is what an app has — nobody presses the star on La Liga and then
 * expects its matches left out.
 *
 * An empty selection matches nothing, deliberately. Somebody who has chosen nothing yet is
 * shown the first-run screen and asked to choose; somebody who removed their last favourite
 * chose an empty agenda and is told so. Neither is quietly handed a list they did not pick.
 *
 * Filtering happens here rather than through the API because the API has no per-caller state:
 * one request for the window, then this — instead of one request per followed team, which on
 * a limit of thirty a minute shared with every device in the house is the difference between
 * a session that works and one that starts refusing.
 */
data class Favorites(
    val teamIds: Set<Int> = emptySet(),
    val competitionIds: Set<Int> = emptySet(),
) {
    val isEmpty: Boolean get() = teamIds.isEmpty() && competitionIds.isEmpty()

    fun covers(event: EventDto): Boolean {
        if (isEmpty) return false
        if (event.competition.id in competitionIds) return true
        return event.local?.id in teamIds || event.visitor?.id in teamIds
    }

    fun filter(events: List<EventDto>): List<EventDto> = events.filter(::covers)

    fun withTeam(id: Int, followed: Boolean): Favorites =
        copy(teamIds = if (followed) teamIds + id else teamIds - id)

    fun withCompetition(id: Int, followed: Boolean): Favorites =
        copy(competitionIds = if (followed) competitionIds + id else competitionIds - id)

    fun followsTeam(id: Int): Boolean = id in teamIds

    fun followsCompetition(id: Int): Boolean = id in competitionIds

    companion object {
        val NONE = Favorites()
    }
}
