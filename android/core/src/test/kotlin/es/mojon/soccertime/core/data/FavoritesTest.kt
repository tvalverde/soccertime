package es.mojon.soccertime.core.data

import es.mojon.soccertime.core.model.CompetitionDto
import es.mojon.soccertime.core.model.EventDto
import es.mojon.soccertime.core.model.TeamDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pinned against `EventQuerySet.for_selection` in `soccertime/models.py`. If that rule
 * changes on the site, one of these should be what says so.
 */
class FavoritesTest {

    private val laLiga = CompetitionDto(id = 10, name = "La Liga EA Sports")
    private val motoGp = CompetitionDto(id = 20, name = "MotoGP")

    private val madrid = TeamDto(id = 1, name = "Real Madrid")
    private val malaga = TeamDto(id = 2, name = "Málaga")
    private val barcelona = TeamDto(id = 3, name = "FC Barcelona")

    private fun match(local: TeamDto, visitor: TeamDto, competition: CompetitionDto = laLiga) =
        EventDto(
            id = local.id * 1000 + visitor.id,
            eventType = "match",
            title = "${local.name} - ${visitor.name}",
            local = local,
            visitor = visitor,
            competition = competition,
            date = "2026-08-30T17:00:00+02:00",
        )

    private fun race(competition: CompetitionDto = motoGp) =
        EventDto(
            id = 99,
            eventType = "race",
            name = "G.P. Aragón (Motorland)",
            competition = competition,
            date = "2026-08-30T14:00:00+02:00",
        )

    @Test
    fun `a followed team counts at home`() {
        val following = Favorites(teamIds = setOf(madrid.id))

        assertTrue(following.covers(match(madrid, malaga)))
    }

    @Test
    fun `and away`() {
        val following = Favorites(teamIds = setOf(madrid.id))

        assertTrue(following.covers(match(malaga, madrid)))
    }

    @Test
    fun `a match between two teams neither of which is followed is not covered`() {
        val following = Favorites(teamIds = setOf(madrid.id))

        assertFalse(following.covers(match(malaga, barcelona)))
    }

    @Test
    fun `a followed competition brings everything in it, matches included`() {
        // The one place a visitor's own list parts company with the owner's curated one:
        // somebody who starred La Liga expects La Liga's matches.
        val following = Favorites(competitionIds = setOf(laLiga.id))

        assertTrue(following.covers(match(malaga, barcelona)))
        assertTrue(following.covers(race(laLiga)))
        assertFalse(following.covers(race(motoGp)))
    }

    @Test
    fun `an event with no teams is covered only through its competition`() {
        assertTrue(Favorites(competitionIds = setOf(motoGp.id)).covers(race()))
        assertFalse(Favorites(teamIds = setOf(madrid.id)).covers(race()))
    }

    @Test
    fun `choosing nothing covers nothing, rather than quietly covering everything`() {
        val chosen = Favorites.NONE

        assertTrue(chosen.isEmpty)
        assertFalse(chosen.covers(match(madrid, malaga)))
        assertFalse(chosen.covers(race()))
        assertEquals(emptyList<EventDto>(), chosen.filter(listOf(match(madrid, malaga), race())))
    }

    @Test
    fun `filtering keeps the order the api sent`() {
        val following = Favorites(teamIds = setOf(madrid.id), competitionIds = setOf(motoGp.id))
        val fromTheApi = listOf(
            match(malaga, barcelona),
            race(),
            match(madrid, malaga),
            match(barcelona, malaga),
        )

        val kept = following.filter(fromTheApi)

        assertEquals(listOf(99, 1002), kept.map(EventDto::id))
    }

    @Test
    fun `following and unfollowing round-trips`() {
        val after = Favorites.NONE
            .withTeam(madrid.id, followed = true)
            .withCompetition(motoGp.id, followed = true)
            .withTeam(barcelona.id, followed = true)
            .withTeam(barcelona.id, followed = false)

        assertEquals(setOf(madrid.id), after.teamIds)
        assertEquals(setOf(motoGp.id), after.competitionIds)
        assertTrue(after.followsTeam(madrid.id))
        assertFalse(after.followsTeam(barcelona.id))
        assertTrue(after.followsCompetition(motoGp.id))
    }

    @Test
    fun `unfollowing something that was never followed changes nothing`() {
        val following = Favorites(teamIds = setOf(madrid.id))

        assertEquals(following, following.withTeam(barcelona.id, followed = false))
    }
}
