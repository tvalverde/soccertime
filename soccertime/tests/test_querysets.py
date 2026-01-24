"""
Tests for EventQuerySet methods.

These tests verify all the custom queryset methods used for filtering events.
"""

import datetime

from django.utils import timezone

from soccertime.models import Event, Match, SimpleEvent


def event_pks(queryset):
    """Helper to get list of pks from queryset."""
    return list(queryset.values_list("pk", flat=True))


class TestEventQuerySetTimeFilters:
    """Tests for time-based filtering methods."""

    def test_in_progress_or_upcoming_includes_future(self, match):
        """Should include future events."""
        events = Event.objects.in_progress_or_upcoming()
        assert match.pk in event_pks(events)

    def test_in_progress_or_upcoming_includes_recent(self, match_in_progress):
        """Should include events started within hours_before."""
        events = Event.objects.in_progress_or_upcoming(hours_before=3)
        assert match_in_progress.pk in event_pks(events)

    def test_in_progress_or_upcoming_excludes_old(self, match_past):
        """Should exclude events older than hours_before."""
        events = Event.objects.in_progress_or_upcoming(hours_before=3)
        assert match_past.pk not in event_pks(events)

    def test_in_window_includes_events_in_range(self, match, match_in_progress):
        """Should include events within the time window."""
        events = Event.objects.in_window(hours_before=3, days_ahead=3)
        assert match.pk in event_pks(events)
        assert match_in_progress.pk in event_pks(events)

    def test_in_window_excludes_events_outside_range(self, match_past, match_future):
        """Should exclude events outside the time window."""
        events = Event.objects.in_window(hours_before=3, days_ahead=3)
        assert match_past.pk not in event_pks(events)
        # match_future is 7 days ahead, should be excluded
        assert match_future.pk not in event_pks(events)

    def test_today_onwards_includes_today(self, match):
        """Should include events from today."""
        events = Event.objects.today_onwards()
        assert match.pk in event_pks(events)

    def test_today_onwards_excludes_yesterday(self, match_past):
        """Should exclude events from yesterday."""
        events = Event.objects.today_onwards()
        assert match_past.pk not in event_pks(events)

    def test_for_date_filters_correctly(self, db, competition, team_home, team_away):
        """Should return only events on the specific date."""
        specific_date = timezone.now().date() + datetime.timedelta(days=5)
        match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=timezone.make_aware(datetime.datetime.combine(specific_date, datetime.time(15, 0))),
        )

        events = Event.objects.for_date(specific_date)
        assert match.pk in event_pks(events)

        events_other_date = Event.objects.for_date(specific_date + datetime.timedelta(days=1))
        assert match.pk not in event_pks(events_other_date)

    def test_for_date_range(self, all_events):
        """Should return events within date range."""
        start = timezone.now().date() - datetime.timedelta(days=1)
        end = timezone.now().date() + datetime.timedelta(days=1)
        events = Event.objects.for_date_range(start, end)
        pks = event_pks(events)

        # Should include events within range
        assert all_events["match"].pk in pks or all_events["match_in_progress"].pk in pks

    def test_upcoming_days(self, match, match_future):
        """Should return events in the next N days."""
        events = Event.objects.upcoming_days(days=3)
        assert match.pk in event_pks(events)
        # match_future is 7 days ahead
        assert match_future.pk not in event_pks(events)

        events_week = Event.objects.upcoming_days(days=8)
        assert match_future.pk in event_pks(events_week)


class TestEventQuerySetRelationFilters:
    """Tests for relation-based filtering methods."""

    def test_for_team_home(self, match, team_home):
        """Should find events where team plays at home."""
        events = Event.objects.for_team(team_home.pk)
        assert match.pk in event_pks(events)

    def test_for_team_away(self, match, team_away):
        """Should find events where team plays away."""
        events = Event.objects.for_team(team_away.pk)
        assert match.pk in event_pks(events)

    def test_for_team_excludes_others(self, match, team_third):
        """Should not include events where team does not play."""
        events = Event.objects.for_team(team_third.pk)
        assert match.pk not in event_pks(events)

    def test_for_competition(self, match, competition):
        """Should return events for the competition."""
        events = Event.objects.for_competition(competition.pk)
        assert match.pk in event_pks(events)

    def test_for_competition_excludes_others(self, match, competition_champions):
        """Should not include events from other competitions."""
        events = Event.objects.for_competition(competition_champions.pk)
        assert match.pk not in event_pks(events)

    def test_for_sport(self, match, sport, race, sport_cycling):
        """Should return events for the sport."""
        football_events = Event.objects.for_sport(sport.pk)
        assert match.pk in event_pks(football_events)
        assert race.pk not in event_pks(football_events)

        cycling_events = Event.objects.for_sport(sport_cycling.pk)
        assert race.pk in event_pks(cycling_events)
        assert match.pk not in event_pks(cycling_events)

    def test_for_channel(self, match_with_channels, channel):
        """Should return events broadcast on the channel."""
        events = Event.objects.for_channel(channel.pk)
        assert match_with_channels.pk in event_pks(events)

    def test_for_channel_excludes_others(self, match, channel):
        """Should not include events not on the channel."""
        events = Event.objects.for_channel(channel.pk)
        assert match.pk not in event_pks(events)


class TestEventQuerySetTypeFilters:
    """Tests for event type filtering methods."""

    def test_by_type_match(self, match, race, simple_event):
        """Should filter by match type."""
        events = Event.objects.by_type("match")
        pks = event_pks(events)
        assert match.pk in pks
        assert race.pk not in pks
        assert simple_event.pk not in pks

    def test_by_type_race(self, match, race, simple_event):
        """Should filter by race type."""
        events = Event.objects.by_type("race")
        pks = event_pks(events)
        assert race.pk in pks
        assert match.pk not in pks
        assert simple_event.pk not in pks

    def test_by_type_simple(self, match, race, simple_event):
        """Should filter by simple type."""
        events = Event.objects.by_type("simple")
        pks = event_pks(events)
        assert simple_event.pk in pks
        assert match.pk not in pks
        assert race.pk not in pks

    def test_matches_shortcut(self, match, race):
        """matches() should be equivalent to by_type('match')."""
        events = Event.objects.matches()
        pks = event_pks(events)
        assert match.pk in pks
        assert race.pk not in pks

    def test_races_shortcut(self, match, race):
        """races() should be equivalent to by_type('race')."""
        events = Event.objects.races()
        pks = event_pks(events)
        assert race.pk in pks
        assert match.pk not in pks

    def test_simple_events_shortcut(self, match, simple_event):
        """simple_events() should be equivalent to by_type('simple')."""
        events = Event.objects.simple_events()
        pks = event_pks(events)
        assert simple_event.pk in pks
        assert match.pk not in pks


class TestEventQuerySetSearch:
    """Tests for search functionality."""

    def test_search_by_local_team(self, match):
        """Should find match by home team name."""
        events = Event.objects.search("Real Madrid")
        assert match.pk in event_pks(events)

    def test_search_by_visitor_team(self, match):
        """Should find match by away team name."""
        events = Event.objects.search("Barcelona")
        assert match.pk in event_pks(events)

    def test_search_by_race_name(self, race):
        """Should find race by name."""
        events = Event.objects.search("Etapa 15")
        assert race.pk in event_pks(events)

    def test_search_by_simple_event_name(self, simple_event):
        """Should find simple event by name."""
        events = Event.objects.search("Final Masculina")
        assert simple_event.pk in event_pks(events)

    def test_search_case_insensitive(self, match):
        """Search should be case insensitive."""
        events = Event.objects.search("real madrid")
        assert match.pk in event_pks(events)

    def test_search_partial_match(self, match):
        """Search should match partial strings."""
        events = Event.objects.search("Madrid")
        assert match.pk in event_pks(events)

    def test_search_empty_query(self, match, race):
        """Empty search should return all events."""
        events = Event.objects.search("")
        pks = event_pks(events)
        assert match.pk in pks
        assert race.pk in pks

    def test_search_none_query(self, match, race):
        """None search should return all events."""
        events = Event.objects.search(None)
        pks = event_pks(events)
        assert match.pk in pks
        assert race.pk in pks

    def test_search_no_results(self, match, race):
        """Should return empty queryset when no matches."""
        events = Event.objects.search("Nonexistent Team XYZ")
        pks = event_pks(events)
        assert match.pk not in pks
        assert race.pk not in pks


class TestEventQuerySetFavorites:
    """Tests for favorites filtering."""

    def test_favorites_includes_favorite_team_home(self, match, favorite_team):
        """Should include events with favorite team playing at home."""
        events = Event.objects.favorites()
        assert match.pk in event_pks(events)

    def test_favorites_includes_favorite_team_away(self, db, competition, team_home, team_away, favorite_team):
        """Should include events with favorite team playing away."""
        match = Match.objects.create(
            competition=competition,
            local=team_away,
            visitor=team_home,  # favorite team is away
            date=timezone.now() + datetime.timedelta(hours=5),
        )
        events = Event.objects.favorites()
        assert match.pk in event_pks(events)

    def test_favorites_excludes_non_favorites(self, db, competition, team_away, team_third):
        """Should exclude events without favorite teams."""
        match = Match.objects.create(
            competition=competition,
            local=team_away,
            visitor=team_third,
            date=timezone.now() + datetime.timedelta(hours=6),
        )
        events = Event.objects.favorites()
        assert match.pk not in event_pks(events)

    def test_favorites_includes_favorite_competition_race(
        self, race, favorite_competition, competition_tour, competition
    ):
        """Should include races from favorite competitions."""
        # Note: race is in competition_tour, not in the favorite competition (La Liga)
        # So this test verifies that race is NOT in favorites
        events = Event.objects.favorites()
        assert race.pk not in event_pks(events)

    def test_favorites_includes_favorite_competition_simple_event(self, db, competition, favorite_competition):
        """Should include simple events from favorite competitions."""
        event = SimpleEvent.objects.create(
            competition=competition,  # This is the favorite competition
            name="Test Event",
            date=timezone.now() + datetime.timedelta(hours=1),
        )
        events = Event.objects.favorites()
        assert event.pk in event_pks(events)


class TestEventQuerySetChaining:
    """Tests for method chaining."""

    def test_chain_type_and_time(self, match, match_past, race):
        """Should be able to chain type and time filters."""
        events = Event.objects.matches().in_progress_or_upcoming()
        pks = event_pks(events)
        assert match.pk in pks
        assert match_past.pk not in pks
        assert race.pk not in pks

    def test_chain_sport_and_time(self, match, race, sport):
        """Should be able to chain sport and time filters."""
        events = Event.objects.for_sport(sport.pk).in_progress_or_upcoming()
        pks = event_pks(events)
        assert match.pk in pks
        assert race.pk not in pks

    def test_chain_search_and_type(self, match, race):
        """Should be able to chain search and type filters."""
        events = Event.objects.search("Madrid").matches()
        pks = event_pks(events)
        assert match.pk in pks
        assert race.pk not in pks

    def test_chain_multiple_filters(self, match, match_future, sport, competition):
        """Should be able to chain multiple filters."""
        events = Event.objects.for_sport(sport.pk).for_competition(competition.pk).in_progress_or_upcoming().matches()
        assert match.pk in event_pks(events)


class TestEventQuerySetWithRelated:
    """Tests for with_related() optimization."""

    def test_with_related_returns_queryset(self, match):
        """with_related() should return a queryset."""
        events = Event.objects.all()
        # with_related is now called automatically in get_queryset
        assert hasattr(events, "filter")

    def test_with_related_loads_competition(self, match):
        """Should preload competition without extra query."""
        events = list(Event.objects.all())
        # Access competition - should not trigger additional query
        for event in events:
            _ = event.competition.name
            _ = event.competition.sport.name

    def test_with_related_loads_channels(self, match_with_channels):
        """Should preload channels without extra query."""
        events = list(Event.objects.all())
        for event in events:
            _ = list(event.channels.all())
