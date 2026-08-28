"""Sports, competitions, teams and flags: the catalogue the listings hang off.

Two things here are worth more than the field lists. The first is that a row whose image
file is gone still serializes: production held 49 flags in exactly that state, and reading
their dimensions from the file is what returned 500 from `/competitions/` once already.
The second is that "favourite" means the same thing here as on the site — any curated row
naming the record — because a client showing a different set than the page would be a bug
nobody could locate.
"""

import pytest
from django.urls import reverse

from soccertime.models import Competition, Favorite


def results(response):
    return response.json()["results"]


def names(response):
    return [row["name"] for row in results(response)]


@pytest.mark.django_db
class TestSports:
    def test_every_sport_is_listed_in_its_own_order(self, client, sports):
        assert names(client.get(reverse("sport-list"))) == ["Fútbol", "Ciclismo", "Tenis"]

    def test_a_sport_carries_what_the_model_holds(self, client, sport):
        payload = client.get(reverse("sport-detail", args=[sport.pk])).json()

        assert payload == {"id": sport.pk, "name": "Fútbol", "order": 1}

    def test_only_the_sports_with_something_coming_when_asked(self, client, match, race_past, sport_tennis):
        """The same question `/competitions/` asks, so both pages can agree."""
        assert names(client.get(reverse("sport-list"), {"with_events": "true"})) == ["Fútbol"]

    def test_the_whole_catalogue_when_not_asked(self, client, match, race_past, sport_tennis):
        assert len(names(client.get(reverse("sport-list")))) == 3

    def test_searching_by_name(self, client, sports):
        assert names(client.get(reverse("sport-list"), {"search": "ten"})) == ["Tenis"]


@pytest.mark.django_db
class TestCompetitions:
    def test_a_competition_carries_its_sport_and_its_flag(self, client, competition):
        payload = client.get(reverse("competition-detail", args=[competition.pk])).json()

        assert payload["name"] == "La Liga"
        assert payload["sport"]["name"] == "Fútbol"
        assert payload["flag"]["display_name"] == "España"

    def test_a_competition_without_a_flag_says_so(self, client, competition_champions):
        payload = client.get(reverse("competition-detail", args=[competition_champions.pk])).json()

        assert payload["flag"] is None

    def test_it_counts_what_is_still_to_come(self, client, competition, match, match_past):
        payload = client.get(reverse("competition-detail", args=[competition.pk])).json()

        assert payload["upcoming_event_count"] == 1

    def test_the_curated_favourites_are_marked(self, client, competition, favorite_competition):
        payload = client.get(reverse("competition-detail", args=[competition.pk])).json()

        assert payload["is_favorite"] is True

    def test_a_competition_nobody_starred_is_not(self, client, competition_champions):
        payload = client.get(reverse("competition-detail", args=[competition_champions.pk])).json()

        assert payload["is_favorite"] is False

    def test_filtering_by_sport(self, client, competition, competition_tour, sport_cycling):
        response = client.get(reverse("competition-list"), {"sport": sport_cycling.pk})

        assert names(response) == ["Tour de Francia"]

    def test_filtering_by_what_still_has_events(self, client, competition, competition_champions, match):
        response = client.get(reverse("competition-list"), {"has_upcoming_events": "true"})

        assert names(response) == ["La Liga"]

    def test_filtering_by_favourite(self, client, competition, competition_champions, favorite_competition):
        response = client.get(reverse("competition-list"), {"favorite": "true"})

        assert names(response) == ["La Liga"]

    def test_searching_by_name(self, client, competition, competition_champions):
        assert names(client.get(reverse("competition-list"), {"search": "liga"})) == ["La Liga"]

    def test_the_listing_is_alphabetical(self, client, competition, competition_champions, competition_tour):
        assert names(client.get(reverse("competition-list"))) == sorted(
            Competition.objects.values_list("name", flat=True)
        )


@pytest.mark.django_db
class TestTeams:
    def test_a_team_carries_its_crest_slot_even_when_empty(self, client, team_home):
        payload = client.get(reverse("team-detail", args=[team_home.pk])).json()

        assert payload["name"] == "Real Madrid"
        assert payload["crest"] is None

    def test_a_crest_reports_its_url_and_the_dimensions_that_were_stored(self, client, team_home):
        team_home.crest.name = "crests/aa/bb/aabbccdd.webp"
        team_home.crest_width, team_home.crest_height = 64, 64
        team_home.save()

        payload = client.get(reverse("team-detail", args=[team_home.pk])).json()

        assert payload["crest"]["url"].endswith("crests/aa/bb/aabbccdd.webp")
        assert (payload["crest"]["width"], payload["crest"]["height"]) == (64, 64)

    def test_a_crest_whose_file_is_gone_is_still_served(self, client, team_home):
        """Production held 49 image rows with no file. Reading one used to raise.

        The dimensions come from the row, never from the file, which is the same reason
        the fields deliberately do not declare `width_field` / `height_field`.
        """
        team_home.crest.name = "crests/ff/ff/nothing-here.webp"
        team_home.save()

        response = client.get(reverse("team-detail", args=[team_home.pk]))

        assert response.status_code == 200
        assert response.json()["crest"]["width"] is None

    def test_filtering_by_favourite(self, client, team_home, team_away, favorite_team):
        response = client.get(reverse("team-list"), {"favorite": "true"})

        assert names(response) == ["Real Madrid"]

    def test_searching_by_name(self, client, teams):
        assert names(client.get(reverse("team-list"), {"search": "barce"})) == ["FC Barcelona"]

    def test_filtering_by_having_a_crest(self, client, team_home, team_away):
        """The strips only show a team that has one, so a client building one needs the same set."""
        team_home.crest.name = "crests/aa/bb/aabbccdd.webp"
        team_home.save()

        assert names(client.get(reverse("team-list"), {"has_crest": "true"})) == ["Real Madrid"]


@pytest.mark.django_db
class TestFlags:
    def test_a_flag_carries_both_of_its_names(self, client, flag):
        payload = client.get(reverse("flag-detail", args=[flag.pk])).json()

        assert (payload["name"], payload["display_name"]) == ("spain", "España")

    def test_a_flag_with_no_image_says_so(self, client, flag):
        assert client.get(reverse("flag-detail", args=[flag.pk])).json()["image"] is None

    def test_searching_by_display_name(self, client, flag, flag_france):
        assert names(client.get(reverse("flag-list"), {"search": "franc"})) == ["france"]


@pytest.mark.django_db
class TestFavorites:
    """The owner's curated list, which is what a visitor who has chosen nothing is shown."""

    def test_it_lists_the_curated_rows_in_their_order(self, client, favorite_competition, favorite_team):
        rows = results(client.get(reverse("favorite-list")))

        assert [row["order"] for row in rows] == [1, 2]

    def test_a_row_names_what_it_points_at(self, client, favorite_competition):
        row = results(client.get(reverse("favorite-list")))[0]

        assert row["competition"]["name"] == "La Liga"
        assert row["team"] is None

    def test_filtering_by_kind(self, client, favorite_competition, favorite_team):
        rows = results(client.get(reverse("favorite-list"), {"kind": "team"}))

        assert [row["team"]["name"] for row in rows] == ["Real Madrid"]

    def test_a_competition_only_favourite_is_not_a_team_favourite(self, client, favorite_competition):
        assert results(client.get(reverse("favorite-list"), {"kind": "team"})) == []

    def test_the_listing_matches_the_table(self, client, favorites):
        assert client.get(reverse("favorite-list")).json()["count"] == Favorite.objects.count()
