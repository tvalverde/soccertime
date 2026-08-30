"""The events listing, which is the whole point of the API.

Two of these tests compare the API against the querysets the site itself is built on
rather than against a literal: `is_favorite` must select what `EventQuerySet.favorites()`
selects and `watchable` what `watchable()` does, because a client that draws a star or a
play button on a different set than the page would be a bug with no visible cause.

The last class pins that the number of queries does not grow with the number of events.
The listing walks competition, sport, flag, both teams, every channel and every link of
each, which is six tables per row: without the prefetching the site already does, a page
of 25 events would cost hundreds of queries against SQLite.
"""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from soccertime.models import Event, Favorite, Match


def results(response):
    return response.json()["results"]


def ids(response):
    return {row["id"] for row in results(response)}


@pytest.fixture
def watchable_match(match, channel_with_links):
    """An event carrying a channel that has an enabled link, which is what a play button means."""
    match.channels.add(channel_with_links)
    return match


@pytest.mark.django_db
class TestWhatAnEventCarries:
    def test_a_match_names_both_teams(self, client, match):
        payload = client.get(reverse("event-detail", args=[match.pk])).json()

        assert payload["event_type"] == "match"
        assert payload["local"]["name"] == "Real Madrid"
        assert payload["visitor"]["name"] == "FC Barcelona"
        assert payload["title"] == "Real Madrid - FC Barcelona"

    def test_a_match_carries_no_name_of_its_own(self, client, match):
        assert client.get(reverse("event-detail", args=[match.pk])).json()["name"] is None

    def test_a_race_carries_its_name_and_no_teams(self, client, race):
        payload = client.get(reverse("event-detail", args=[race.pk])).json()

        assert payload["event_type"] == "race"
        assert payload["name"] == "Etapa 15 - Montaña"
        assert payload["title"] == "Etapa 15 - Montaña"
        assert payload["local"] is None and payload["visitor"] is None

    def test_a_simple_event_carries_its_name(self, client, simple_event):
        payload = client.get(reverse("event-detail", args=[simple_event.pk])).json()

        assert payload["event_type"] == "simple"
        assert payload["name"] == "Final Masculina"

    def test_an_event_carries_its_competition_and_sport(self, client, match):
        payload = client.get(reverse("event-detail", args=[match.pk])).json()

        assert payload["competition"]["name"] == "La Liga"
        assert payload["competition"]["sport"]["name"] == "Fútbol"

    def test_an_event_carries_its_details(self, client, race):
        assert client.get(reverse("event-detail", args=[race.pk])).json()["details"] == (
            "Etapa de alta montaña con 3 puertos"
        )

    def test_an_event_carries_the_channels_it_is_on(self, client, match_with_channels):
        payload = client.get(reverse("event-detail", args=[match_with_channels.pk])).json()

        assert {channel["name"] for channel in payload["channels"]} == {"Movistar LaLiga", "DAZN"}

    def test_an_event_says_when_it_ends(self, client, match):
        """Two hours unless the row says otherwise, which is what the site assumes too."""
        payload = client.get(reverse("event-detail", args=[match.pk])).json()

        assert payload["duration"] is None
        assert datetime.datetime.fromisoformat(payload["date_end"]) - datetime.datetime.fromisoformat(
            payload["date"]
        ) == datetime.timedelta(hours=2)

    def test_a_custom_duration_is_honoured(self, client, race):
        race.duration = datetime.timedelta(hours=5)
        race.save()

        payload = client.get(reverse("event-detail", args=[race.pk])).json()

        assert datetime.datetime.fromisoformat(payload["date_end"]) - datetime.datetime.fromisoformat(
            payload["date"]
        ) == datetime.timedelta(hours=5)


@pytest.mark.django_db
class TestTimesAreReadTheWayTheSiteReadsThem:
    """The source publishes peninsular time and every visitor is shown that clock.

    An API answering in UTC would be correct and would still make every client re-derive
    the day an event belongs to — which is the bug `today_onwards()` documents, moved to
    the other side of the wire. The offset travels with the value, so nothing is ambiguous.
    """

    def test_the_instant_is_the_one_that_was_stored(self, client, match):
        payload = client.get(reverse("event-detail", args=[match.pk])).json()

        assert datetime.datetime.fromisoformat(payload["date"]) == match.date

    def test_it_is_expressed_in_the_timezone_the_site_is_read_in(self, client, match):
        payload = client.get(reverse("event-detail", args=[match.pk])).json()

        assert (
            datetime.datetime.fromisoformat(payload["date"]).utcoffset() == timezone.localtime(match.date).utcoffset()
        )


@pytest.mark.django_db
class TestTheListing:
    def test_it_is_chronological(self, client, all_events):
        dates = [row["date"] for row in results(client.get(reverse("event-list"), {"page_size": 100}))]

        assert dates == sorted(dates)

    def test_it_can_be_reversed(self, client, all_events):
        dates = [
            row["date"] for row in results(client.get(reverse("event-list"), {"ordering": "-date", "page_size": 100}))
        ]

        assert dates == sorted(dates, reverse=True)

    def test_an_unknown_ordering_is_refused(self, client):
        assert client.get(reverse("event-list"), {"ordering": "name"}).status_code == 400

    def test_it_holds_every_event_by_default(self, client, all_events):
        """Including what has already happened: an archive is information the site holds."""
        assert client.get(reverse("event-list")).json()["count"] == Event.objects.count()


@pytest.mark.django_db
class TestFilteringByTime:
    def test_only_what_is_still_to_come(self, client, all_events):
        listed = ids(client.get(reverse("event-list"), {"upcoming": "true", "page_size": 100}))

        assert all_events["match_past"].pk not in listed
        assert all_events["match"].pk in listed

    def test_an_event_in_progress_counts_as_upcoming(self, client, match_in_progress):
        """It started an hour ago and is still on; the site's listings keep it for three."""
        assert ids(client.get(reverse("event-list"), {"upcoming": "true"})) == {match_in_progress.pk}

    def test_from_the_start_of_today(self, client, match, match_past):
        listed = ids(client.get(reverse("event-list"), {"today_onwards": "true"}))

        assert listed == {match.pk}

    def test_one_named_day(self, client, match, match_future):
        day = timezone.localtime(match.date).date().isoformat()

        assert ids(client.get(reverse("event-list"), {"date": day})) == {match.pk}

    def test_a_range_of_days(self, client, match, match_future, match_past):
        today = timezone.localdate()
        response = client.get(
            reverse("event-list"),
            {"date_from": today.isoformat(), "date_to": (today + datetime.timedelta(days=1)).isoformat()},
        )

        assert ids(response) == {match.pk}

    def test_a_range_open_at_the_end(self, client, match, match_past):
        assert ids(client.get(reverse("event-list"), {"date_from": timezone.localdate().isoformat()})) == {match.pk}


@pytest.mark.django_db
class TestFilteringByWhatIsPlaying:
    def test_by_kind(self, client, all_events):
        listed = ids(client.get(reverse("event-list"), {"event_type": "race", "page_size": 100}))

        assert listed == {all_events["race"].pk, all_events["race_past"].pk}

    def test_by_competition(self, client, match, race):
        assert ids(client.get(reverse("event-list"), {"competition": match.competition.pk})) == {match.pk}

    def test_by_sport(self, client, match, race, sport_cycling):
        assert ids(client.get(reverse("event-list"), {"sport": sport_cycling.pk})) == {race.pk}

    def test_by_team_at_home_or_away(self, client, match, match_past, race, team_home):
        listed = ids(client.get(reverse("event-list"), {"team": team_home.pk, "page_size": 100}))

        assert listed == {match.pk, match_past.pk}

    def test_by_channel(self, client, match_with_channels, race, channel):
        assert ids(client.get(reverse("event-list"), {"channel": channel.pk})) == {match_with_channels.pk}

    def test_by_search_over_the_names_a_visitor_types(self, client, match, race):
        assert ids(client.get(reverse("event-list"), {"search": "barcelona"})) == {match.pk}

    def test_search_reaches_the_competition_and_the_sport(self, client, match, race):
        """The box was useless without these: "LaLiga" and "Ciclismo" returned nothing."""
        assert ids(client.get(reverse("event-list"), {"search": "liga"})) == {match.pk}
        assert ids(client.get(reverse("event-list"), {"search": "ciclismo"})) == {race.pk}


@pytest.mark.django_db
class TestWatchable:
    def test_an_event_with_an_enabled_link_says_so(self, client, watchable_match):
        assert client.get(reverse("event-detail", args=[watchable_match.pk])).json()["watchable"] is True

    def test_an_event_whose_channel_carries_nothing_does_not(self, client, match_with_channels):
        assert client.get(reverse("event-detail", args=[match_with_channels.pk])).json()["watchable"] is False

    def test_a_disabled_link_does_not_make_an_event_watchable(self, client, match, channel, channel_link_disabled):
        channel.links.add(channel_link_disabled)
        match.channels.add(channel)

        assert client.get(reverse("event-detail", args=[match.pk])).json()["watchable"] is False

    def test_the_filter_selects_exactly_what_the_field_marks(self, client, watchable_match, race, match_past):
        listed = ids(client.get(reverse("event-list"), {"watchable": "true", "page_size": 100}))

        assert listed == set(Event.objects.watchable().values_list("pk", flat=True))
        assert listed == {watchable_match.pk}


@pytest.mark.django_db
class TestFavorites:
    def test_a_match_of_a_favourite_team_is_marked(self, client, match, favorite_team):
        assert client.get(reverse("event-detail", args=[match.pk])).json()["is_favorite"] is True

    def test_a_race_of_a_favourite_competition_is_marked(self, client, race, competition_tour):
        Favorite.objects.create(competition=competition_tour, order=1)

        assert client.get(reverse("event-detail", args=[race.pk])).json()["is_favorite"] is True

    def test_an_event_nobody_starred_is_not(self, client, match):
        assert client.get(reverse("event-detail", args=[match.pk])).json()["is_favorite"] is False

    def test_the_filter_selects_exactly_what_the_field_marks(self, client, all_events, favorite_team):
        listed = ids(client.get(reverse("event-list"), {"favorites": "true", "page_size": 100}))

        assert listed == set(Event.objects.favorites().values_list("pk", flat=True))

    def test_the_field_agrees_with_the_filter_row_by_row(self, client, all_events, favorite_team):
        """The two are computed by different means — Python over a prefetch, and SQL."""
        selected = set(Event.objects.favorites().values_list("pk", flat=True))
        marked = {
            row["id"] for row in results(client.get(reverse("event-list"), {"page_size": 100})) if row["is_favorite"]
        }

        assert marked == selected


@pytest.mark.django_db
class TestTheListingDoesNotQueryPerRow:
    def queries_for(self, client, url):
        with CaptureQueriesContext(connection) as captured:
            assert client.get(url).status_code == 200
        return len(captured.captured_queries)

    def add_events(self, competition, teams, channel, count, offset=0):
        for index in range(count):
            match = Match.objects.create(
                competition=competition,
                local=teams[index % len(teams)],
                visitor=teams[(index + 1) % len(teams)],
                date=timezone.now() + datetime.timedelta(days=offset + index + 1),
            )
            match.channels.add(channel)

    def test_the_count_does_not_grow_with_the_number_of_events(self, client, competition, teams, channel_with_links):
        url = f"{reverse('event-list')}?page_size=100"
        self.add_events(competition, teams, channel_with_links, count=1)
        with_one = self.queries_for(client, url)

        self.add_events(competition, teams, channel_with_links, count=9, offset=10)
        with_ten = self.queries_for(client, url)

        assert with_ten == with_one


@pytest.mark.django_db
class TestTheDaysACalendarLights:
    """`/events/days/`: which local days hold something, under the listing's own filters."""

    def days(self, client, **params):
        return client.get(reverse("event-days"), params).json()["days"]

    def test_every_local_day_with_an_event_appears_exactly_once(self, client, match, race):
        expected = sorted({timezone.localtime(event.date).date().isoformat() for event in Event.objects.all()})

        assert self.days(client) == expected

    def test_a_busy_day_is_still_one_day(self, client, match):
        Match.objects.create(
            competition=match.competition,
            local=match.local,
            visitor=match.visitor,
            date=match.date + datetime.timedelta(hours=1),
        )

        assert len(self.days(client)) == len({timezone.localtime(e.date).date() for e in Event.objects.all()})

    def test_the_listing_filters_narrow_it_too(self, client, match, race):
        theirs = self.days(client, team=match.local.pk)

        assert theirs == [timezone.localtime(match.date).date().isoformat()]
        assert self.days(client, competition=race.competition.pk) == [timezone.localtime(race.date).date().isoformat()]

    def test_days_are_read_in_madrid_not_utc(self, client, race):
        # 23:30 UTC in January is 00:30 of the NEXT day in Madrid.
        race.date = datetime.datetime(2026, 1, 10, 23, 30, tzinfo=datetime.UTC)
        race.save()

        assert self.days(client, date_from="2026-01-01", date_to="2026-01-31") == ["2026-01-11"]

    def test_a_value_that_cannot_be_read_is_refused(self, client):
        response = client.get(reverse("event-days"), {"date_from": "someday"})

        assert response.status_code == 400
