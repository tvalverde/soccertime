"""The page that answers "what do I follow?", which nothing answered before.

A visitor's favourites live in a signed `httponly` cookie. The star on a team's own page
could only ever remove one the visitor already remembered and navigated back to, and no
script could read the cookie to list them, so a selection made and forgotten was a selection
that could not be undone. This page shows it and edits it.

The tests that matter here are the ones about coming back. A star pressed on this page must
return to this page, keeping the tab and the search, or editing four favourites becomes four
journeys through four team pages. And the way back is a literal the view compares — never a
URL out of the request, which on a form any page can post to would be an open redirect.
"""

import pytest
from django.urls import reverse

from soccertime.models import Competition, Sport, Team
from soccertime.visitor_favorites import COOKIE_NAME, Selection, write_selection


@pytest.fixture
def teams(db):
    return [Team.objects.create(name=name) for name in ("FC Barcelona", "Real Madrid", "CD Castellón")]


@pytest.fixture
def competition(db):
    sport = Sport.objects.create(name="Fútbol")
    return Competition.objects.create(name="La Liga EA Sports", sport=sport)


def carrying(client, selection):
    """Give the test client a cookie the view will accept, signed as the site signs it."""
    from django.http import HttpResponse

    signed = write_selection(HttpResponse(), selection)
    client.cookies[COOKIE_NAME] = signed.cookies[COOKIE_NAME].value
    return client


class TestItShowsWhatIsFollowed:
    def test_the_followed_teams_are_listed(self, client, teams):
        carrying(client, Selection(teams=(teams[0].pk, teams[2].pk)))

        body = client.get(reverse("edit-favorites")).content.decode()

        assert "FC Barcelona" in body
        assert "CD Castellón" in body
        assert "Real Madrid" not in body, "a team nobody follows is not on the list of followed ones"

    def test_a_visitor_with_no_selection_is_told_so_rather_than_shown_somebody_else_s(self, client, teams):
        """`/favorites/` falls back to the owner's picks; this page must not."""
        body = client.get(reverse("edit-favorites")).content.decode()

        assert "No sigues ningún equipo" in body

    def test_the_competitions_tab_lists_competitions(self, client, competition):
        carrying(client, Selection(competitions=(competition.pk,)))

        body = client.get(reverse("edit-favorites"), {"kind": "competitions"}).content.decode()

        assert "La Liga EA Sports" in body


class TestSearching:
    def test_it_finds_by_part_of_the_name(self, client, teams):
        body = client.get(reverse("edit-favorites"), {"q": "barcel"}).content.decode()

        assert "FC Barcelona" in body
        assert "Real Madrid" not in body

    def test_one_letter_is_not_a_query(self, client, teams):
        """It would match thousands of the 4,796 teams and answer nothing."""
        body = client.get(reverse("edit-favorites"), {"q": "a"}).content.decode()

        assert "Real Madrid" not in body

    def test_a_result_already_followed_shows_its_star_pressed(self, client, teams):
        carrying(client, Selection(teams=(teams[0].pk,)))

        body = client.get(reverse("edit-favorites"), {"q": "barcel"}).content.decode()

        assert 'aria-pressed="true"' in body


class TestPressingAStarComesBackHere:
    def test_it_returns_to_this_page_and_not_to_the_team_s(self, client, teams):
        response = client.post(reverse("toggle-favorite-team", args=[teams[0].pk]), {"back": "edit"})

        assert response.status_code == 302
        assert response["Location"] == reverse("edit-favorites")

    def test_it_keeps_the_tab_and_the_search(self, client, competition):
        response = client.post(
            reverse("toggle-favorite-competition", args=[competition.pk]),
            {"back": "edit", "kind": "competitions", "q": "liga"},
        )

        assert "kind=competitions" in response["Location"]
        assert "q=liga" in response["Location"]

    def test_without_the_marker_it_still_goes_to_the_entity_s_own_page(self, client, teams):
        """Every star outside this page keeps behaving exactly as it did."""
        response = client.post(reverse("toggle-favorite-team", args=[teams[0].pk]))

        assert response["Location"] == reverse("team-events", args=[teams[0].pk])

    def test_a_url_in_the_request_is_never_followed(self, client, teams):
        """`next=` on a form any page can post to is an open redirect; there is none."""
        response = client.post(
            reverse("toggle-favorite-team", args=[teams[0].pk]),
            {"back": "edit", "next": "https://example.com/", "q": "https://example.com/"},
        )

        # The value survives as a search term, which is harmless and correct. What matters is
        # that the destination is this site's own path and was never taken from the request.
        assert response["Location"].startswith(reverse("edit-favorites"))

    def test_the_star_actually_changes_what_is_followed(self, client, teams):
        carrying(client, Selection(teams=(teams[0].pk,)))

        client.post(reverse("toggle-favorite-team", args=[teams[0].pk]), {"back": "edit"})
        body = client.get(reverse("edit-favorites")).content.decode()

        assert "No sigues ningún equipo" in body


class TestTheWayIn:
    def test_the_favourites_page_offers_the_link(self, client, teams):
        carrying(client, Selection(teams=(teams[0].pk,)))

        body = client.get(reverse("favorites")).content.decode()

        assert reverse("edit-favorites") in body
        assert "Editar mis favoritos" in body

    def test_a_visitor_seeing_the_owner_s_picks_is_told(self, client, teams):
        body = client.get(reverse("favorites")).content.decode()

        assert "no los tuyos" in body
        assert "Elegir mis favoritos" in body

    def test_the_plain_agenda_carries_neither(self, client, teams):
        """The same template renders `/agenda/`, which is nobody's favourites."""
        body = client.get(reverse("agenda")).content.decode()

        assert "Editar mis favoritos" not in body
        assert "no los tuyos" not in body
