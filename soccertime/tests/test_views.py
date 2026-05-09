"""
Tests for soccertime views.

Tests cover:
- HTTP response codes
- Template rendering
- Context data
- Filtering and pagination
- Empty states
"""

import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from soccertime.models import Match, Team


@pytest.fixture
def client():
    """Django test client."""
    return Client()


def get_event_pks(context_events):
    """Extract pks from context events (handles both querysets and Page objects)."""
    if hasattr(context_events, "object_list"):
        # It's a Page object
        return [e.pk for e in context_events.object_list]
    else:
        # It's a queryset
        return list(context_events.values_list("pk", flat=True))


class TestFavoritesView:
    """Tests for favorites view."""

    def test_renders_successfully(self, client, db):
        """Should return 200 status code."""
        response = client.get(reverse("favorites"))
        assert response.status_code == 200

    def test_uses_correct_template(self, client, db):
        """Should use agenda.html template."""
        response = client.get(reverse("favorites"))
        assert "soccertime/agenda.html" in [t.name for t in response.templates]

    def test_shows_favorite_events(self, client, match, favorite_team):
        """Should display events with favorite teams."""
        response = client.get(reverse("favorites"))
        assert match.pk in get_event_pks(response.context["events"])

    def test_empty_state_message(self, client, db):
        """Should show message when no favorite events."""
        response = client.get(reverse("favorites"))
        messages = list(response.context["messages"])
        assert len(messages) == 1
        assert "No hay eventos" in str(messages[0])

    def test_context_has_competitions(self, client, favorite_competition):
        """Should have favorite competitions in context."""
        response = client.get(reverse("favorites"))
        assert "competitions" in response.context


class TestAgendaView:
    """Tests for agenda view."""

    def test_renders_successfully(self, client, db):
        """Should return 200 status code."""
        response = client.get(reverse("agenda"))
        assert response.status_code == 200

    def test_uses_correct_template(self, client, db):
        """Should use agenda.html template."""
        response = client.get(reverse("agenda"))
        assert "soccertime/agenda.html" in [t.name for t in response.templates]

    def test_shows_upcoming_events(self, client, match):
        """Should display upcoming events."""
        response = client.get(reverse("agenda"))
        assert match.pk in get_event_pks(response.context["events"])

    def test_excludes_past_events(self, client, match_past):
        """Should not display past events by default."""
        response = client.get(reverse("agenda"))
        # match_past is from yesterday, should be excluded from today_onwards
        assert match_past.pk not in get_event_pks(response.context["events"])

    def test_filter_by_date(self, client, db, competition, team_home, team_away):
        """Should filter events by date parameter."""
        future_date = timezone.now().date() + datetime.timedelta(days=10)
        match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=timezone.make_aware(datetime.datetime.combine(future_date, datetime.time(20, 0))),
        )

        response = client.get(reverse("agenda"), {"events-date": str(future_date)})
        assert match.pk in get_event_pks(response.context["events"])

    def test_search_filter(self, client, match):
        """Should filter events by search query."""
        response = client.get(reverse("agenda"), {"search": "Real Madrid"})
        assert match.pk in get_event_pks(response.context["events"])

    def test_search_no_results(self, client, match):
        """Should return empty when search has no matches."""
        response = client.get(reverse("agenda"), {"search": "Nonexistent XYZ"})
        assert match.pk not in get_event_pks(response.context["events"])

    def test_pagination(self, client, db, competition, team_home, team_away):
        """Should paginate results."""
        # Create 30 matches to exceed default page size (25)
        teams = []
        for i in range(30):
            team = Team.objects.create(name=f"Team {i}")
            teams.append(team)

        for i in range(30):
            Match.objects.create(
                competition=competition,
                local=team_home,
                visitor=teams[i],
                date=timezone.now() + datetime.timedelta(hours=i + 1),
            )

        response = client.get(reverse("agenda"))
        assert response.context["events"].paginator.num_pages > 1

    def test_context_has_max_date(self, client, match):
        """Should have max_date in context."""
        response = client.get(reverse("agenda"))
        assert "max_date" in response.context

    def test_context_has_teams(self, client, db):
        """Should have teams in context."""
        response = client.get(reverse("agenda"))
        assert "teams" in response.context

    def test_agenda_channels_performance(self, client, db, competition, team_home, team_away):
        """Should have a constant number of queries regardless of the number of channels/links."""
        from soccertime.models import Channel, ChannelLink, ChannelLinkSource, Match

        source = ChannelLinkSource.objects.create(name="perf-test")
        now = timezone.now()

        # Create 3 events, each with 3 channels, each with 2 links
        for i in range(3):
            match = Match.objects.create(
                competition=competition, local=team_home, visitor=team_away, date=now + datetime.timedelta(hours=i + 1)
            )
            for j in range(3):
                ch = Channel.objects.create(name=f"Channel {i}-{j}")
                for k in range(2):
                    link = ChannelLink.objects.create(name=f"Link {i}-{j}-{k}", link="http://example.com", enabled=True)
                    link.sources.add(source)
                    ch.links.add(link)
                match.channels.add(ch)

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as queries:
            client.get(reverse("agenda"))

        # Current state: many queries due to N+1 in channels_list.html
        # Goal after optimization: < 15 queries total
        # We set it higher now to see it "pass" but we know it's inefficient.
        # Actually, let's set a strict limit to see it FAIL first (TDD).
        assert len(queries) < 15


class TestTeamEventsView:
    """Tests for team_events view."""

    def test_renders_successfully(self, client, team_home):
        """Should return 200 status code."""
        response = client.get(reverse("team-events", args=[team_home.pk]))
        assert response.status_code == 200

    def test_404_for_nonexistent_team(self, client, db):
        """Should return 404 for nonexistent team."""
        response = client.get(reverse("team-events", args=[99999]))
        assert response.status_code == 404

    def test_shows_team_events(self, client, match, team_home):
        """Should display events for the team."""
        response = client.get(reverse("team-events", args=[team_home.pk]))
        assert match.pk in get_event_pks(response.context["events"])

    def test_context_has_events_title(self, client, match, team_home):
        """Should have team name as events_title."""
        response = client.get(reverse("team-events", args=[team_home.pk]))
        assert response.context["events_title"] == team_home.name

    def test_context_has_competition_teams(self, client, match, team_home):
        """Should have opponent teams in context."""
        response = client.get(reverse("team-events", args=[team_home.pk]))
        assert "competition_teams" in response.context

    def test_team_events_queries_performance(self, client, db, team_home, team_away, team_third, competition):
        """Should have a constant number of queries regardless of the number of matches."""
        # Create several matches
        now = timezone.now()
        for i in range(10):
            opponent = team_away if i % 2 == 0 else team_third
            Match.objects.create(
                competition=competition,
                local=team_home,
                visitor=opponent,
                date=now + datetime.timedelta(days=i + 1),
            )

        # Measure queries. Without select_related, this would be N queries (one per match to fetch visitor)
        # plus the base queries.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as queries:
            client.get(reverse("team-events", args=[team_home.pk]))

        # We expect a low number of queries. If N+1 exists, it will be around 15-20.
        # If optimized, it should be around 5-8.
        assert len(queries) < 10


class TestChannelEventsView:
    """Tests for channel_events view."""

    def test_renders_successfully(self, client, channel):
        """Should return 200 status code."""
        response = client.get(reverse("channel-events", args=[channel.pk]))
        assert response.status_code == 200

    def test_404_for_nonexistent_channel(self, client, db):
        """Should return 404 for nonexistent channel."""
        response = client.get(reverse("channel-events", args=[99999]))
        assert response.status_code == 404

    def test_shows_channel_events(self, client, match_with_channels, channel):
        """Should display events for the channel."""
        response = client.get(reverse("channel-events", args=[channel.pk]))
        assert match_with_channels.pk in get_event_pks(response.context["events"])

    def test_context_has_events_title(self, client, channel):
        """Should have channel name as events_title."""
        response = client.get(reverse("channel-events", args=[channel.pk]))
        assert response.context["events_title"] == channel.name

    def test_uses_correct_template(self, client, channel):
        """Should use agenda.html template."""
        response = client.get(reverse("channel-events", args=[channel.pk]))
        assert "soccertime/agenda.html" in [t.name for t in response.templates]


class TestSportEventsView:
    """Tests for sport_events view."""

    def test_renders_successfully(self, client, sport):
        """Should return 200 status code."""
        response = client.get(reverse("sport-events", args=[sport.pk]))
        assert response.status_code == 200

    def test_404_for_nonexistent_sport(self, client, db):
        """Should return 404 for nonexistent sport."""
        response = client.get(reverse("sport-events", args=[99999]))
        assert response.status_code == 404

    def test_shows_sport_events(self, client, match, sport):
        """Should display events for the sport."""
        response = client.get(reverse("sport-events", args=[sport.pk]))
        assert match.pk in get_event_pks(response.context["events"])

    def test_excludes_other_sports(self, client, race, sport):
        """Should not display events from other sports."""
        response = client.get(reverse("sport-events", args=[sport.pk]))
        assert race.pk not in get_event_pks(response.context["events"])

    def test_uses_correct_template(self, client, sport):
        """Should use agenda.html template."""
        response = client.get(reverse("sport-events", args=[sport.pk]))
        assert "soccertime/agenda.html" in [t.name for t in response.templates]


class TestCompetitionEventsView:
    """Tests for competition_events view."""

    def test_renders_successfully(self, client, competition):
        """Should return 200 status code."""
        response = client.get(reverse("competition-events", args=[competition.pk]))
        assert response.status_code == 200

    def test_404_for_nonexistent_competition(self, client, db):
        """Should return 404 for nonexistent competition."""
        response = client.get(reverse("competition-events", args=[99999]))
        assert response.status_code == 404

    def test_shows_competition_events(self, client, match, competition):
        """Should display events for the competition."""
        response = client.get(reverse("competition-events", args=[competition.pk]))
        assert match.pk in get_event_pks(response.context["events"])

    def test_context_has_competition_teams(self, client, match, competition):
        """Should have teams in the competition."""
        response = client.get(reverse("competition-events", args=[competition.pk]))
        assert "competition_teams" in response.context


class TestChannelsView:
    """Tests for channels view."""

    def test_renders_successfully(self, client, db):
        """Should return 200 status code."""
        response = client.get(reverse("channels"))
        assert response.status_code == 200

    def test_uses_correct_template(self, client, db):
        """Should use channels.html template."""
        response = client.get(reverse("channels"))
        assert "soccertime/channels.html" in [t.name for t in response.templates]

    def test_shows_channel_links(self, client, channel_link):
        """Should display channel links."""
        response = client.get(reverse("channels"))
        assert channel_link in response.context["channels_links"]

    def test_empty_state_message(self, client, db):
        """Should show message when no channels."""
        response = client.get(reverse("channels"))
        messages = list(response.context["messages"])
        assert len(messages) == 1
        assert "No hay canales" in str(messages[0])


class TestCompetitionsView:
    """Tests for competitions view."""

    def test_renders_successfully(self, client, db):
        """Should return 200 status code."""
        response = client.get(reverse("competitions"))
        assert response.status_code == 200

    def test_uses_correct_template(self, client, db):
        """Should use competitions.html template."""
        response = client.get(reverse("competitions"))
        assert "soccertime/competitions.html" in [t.name for t in response.templates]

    def test_shows_sports_with_events(self, client, match, sport):
        """Should display sports that have events."""
        response = client.get(reverse("competitions"))
        sports = [item["sport"] for item in response.context["sports_data"]]
        assert sport in sports

    def test_excludes_sports_without_events(self, client, sport_tennis):
        """Should not display sports without events."""
        response = client.get(reverse("competitions"))
        sports = [item["sport"] for item in response.context["sports_data"]]
        assert sport_tennis not in sports

    def test_competitions_queries_performance(self, client, db, competition, team_home, team_away):
        """Should have a constant number of queries regardless of the number of sports and competitions."""
        # Create 5 sports, each with 3 competitions, each with 2 events
        from soccertime.models import Competition, Flag, Match, Sport

        now = timezone.now()
        flag = Flag.objects.create(name="testflag")

        for i in range(5):
            s = Sport.objects.create(name=f"Sport {i}", order=i)
            for j in range(3):
                c = Competition.objects.create(name=f"Comp {i}-{j}", sport=s, flag=flag)
                for k in range(2):
                    Match.objects.create(
                        competition=c, local=team_home, visitor=team_away, date=now + datetime.timedelta(days=k + 1)
                    )

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as queries:
            client.get(reverse("competitions"))

        # Without optimization, this would be dozens of queries.
        # With proper pre-fetching and pre-calculation, it should be under 10.
        assert len(queries) < 15


class TestRedirects:
    """Tests for redirect URLs."""

    def test_root_redirects_to_favorites(self, client, db):
        """Root URL should redirect to favorites."""
        response = client.get("/")
        assert response.status_code == 302
        assert response.url == "favorites/"

    def test_events_redirects_to_favorites(self, client, db):
        """Events URL should redirect to favorites."""
        response = client.get("/events/")
        assert response.status_code == 302
        assert "favorites" in response.url
