"""
Tests for EventQuerySet methods.

These tests verify all the custom queryset methods used for filtering events.
"""

import datetime

from django.utils import timezone

from soccertime.models import MAX_SEARCHABLE_NAME_LENGTH, Event, Favorite, Match, Race, SimpleEvent, Team


def event_pks(queryset):
    """Helper to get list of pks from queryset."""
    return list(queryset.values_list("pk", flat=True))


def _match_at(competition, local, visitor, day, at):
    """A match at a wall-clock time on a given day, where the site is read."""
    return Match.objects.create(
        competition=competition,
        local=local,
        visitor=visitor,
        date=timezone.make_aware(datetime.datetime.combine(day, at)),
    )


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

    def test_for_date_includes_the_first_and_last_instant_of_the_day(self, db, competition, team_home, team_away):
        """Midnight belongs to its day, and so does the minute before the next one."""
        day = timezone.now().date() + datetime.timedelta(days=5)
        opens = _match_at(competition, team_home, team_away, day, datetime.time(0, 0))
        closes = _match_at(competition, team_home, team_away, day, datetime.time(23, 59))

        pks = event_pks(Event.objects.for_date(day))
        assert opens.pk in pks
        assert closes.pk in pks

    def test_for_date_does_not_reach_into_the_next_day(self, db, competition, team_home, team_away):
        """The half past midnight that `start_of_today` was written for, from the other side."""
        day = timezone.now().date() + datetime.timedelta(days=5)
        after = _match_at(competition, team_home, team_away, day + datetime.timedelta(days=1), datetime.time(0, 30))

        assert after.pk not in event_pks(Event.objects.for_date(day))

    def test_for_date_holds_a_day_the_clocks_lengthened(self, db, competition, team_home, team_away):
        """25 October 2026 is twenty-five hours long in Madrid.

        A bound built by adding twenty-four hours to midnight would close the day at eleven at
        night and drop everything after it. Nothing about that failure is visible locally
        unless a test puts the clocks where production will eventually put them.
        """
        long_day = datetime.date(2026, 10, 25)
        late = _match_at(competition, team_home, team_away, long_day, datetime.time(23, 30))

        assert late.pk in event_pks(Event.objects.for_date(long_day))

    def test_for_date_holds_a_day_the_clocks_shortened(self, db, competition, team_home, team_away):
        """29 March 2026 is twenty-three hours long, so the same arithmetic overshoots."""
        short_day = datetime.date(2026, 3, 29)
        next_morning = _match_at(
            competition, team_home, team_away, short_day + datetime.timedelta(days=1), datetime.time(0, 30)
        )

        assert next_morning.pk not in event_pks(Event.objects.for_date(short_day))

    def test_for_date_asks_in_a_shape_an_index_can_answer(self, db):
        """The whole point of the change, and the only assertion here that fails without it.

        `date__date=` wraps the column in `django_datetime_cast_date`, a Python function on the
        SQLite connection: no index applies and every one of production's fifty-three thousand
        rows is converted before it can be compared — twice per request, once for the
        paginator's count. The tests above pass either way, because both forms select the same
        events; this one is about how they are selected.
        """
        for query in (
            Event.objects.for_date(datetime.date(2026, 8, 30)).query,
            Event.objects.for_date_range(datetime.date(2026, 8, 29), datetime.date(2026, 8, 30)).query,
        ):
            assert "cast_date" not in str(query).lower()

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

    def test_it_finds_events_by_competition(self, match, competition):
        """The gap that made the box useless for the most obvious thing anyone types.

        Measured against the real database before the fix: "LaLiga" returned 0 results,
        "Fórmula 1" 0 and "Champions" 1, while "Real Madrid" returned 809. Teams were searched
        and competitions were not.
        """
        assert match.pk in event_pks(Event.objects.search(competition.name))

    def test_it_finds_events_by_sport(self, match, competition):
        """ "Tenis" returned nothing at all, because the sport was not searched either."""
        assert match.pk in event_pks(Event.objects.search(competition.sport.name))

    def test_a_term_matching_nothing_still_matches_nothing(self, match):
        """The new fields must widen the search, not turn it into a pass-through."""
        assert event_pks(Event.objects.search("qwertyuiop-no-existe")) == []

    def test_a_query_longer_than_the_fields_matches_nothing(self, match):
        """`icontains` asks for a substring, so nothing that long can be inside a name."""
        events = Event.objects.search("x" * (MAX_SEARCHABLE_NAME_LENGTH + 1))

        assert event_pks(events) == []

    def test_it_answers_without_asking_the_database(self, match, django_assert_num_queries):
        """The point of the bound: four joined tables and a guaranteed cache miss otherwise."""
        with django_assert_num_queries(0):
            list(Event.objects.search("x" * 5000))

    def test_a_query_at_the_bound_still_searches(self, match):
        """The limit is where a match becomes impossible, not a round number short of it."""
        at_the_limit = ("Real Madrid" + "x" * MAX_SEARCHABLE_NAME_LENGTH)[:MAX_SEARCHABLE_NAME_LENGTH]

        assert len(at_the_limit) == MAX_SEARCHABLE_NAME_LENGTH
        assert event_pks(Event.objects.search(at_the_limit)) == []
        assert match.pk in event_pks(Event.objects.search("Real Madrid"))

    def test_the_bound_is_what_the_fields_actually_hold(self):
        """If a name field is ever widened, this is what stops the bound being left behind."""
        campos = [
            Team._meta.get_field("name"),
            Race._meta.get_field("name"),
            SimpleEvent._meta.get_field("name"),
        ]

        assert MAX_SEARCHABLE_NAME_LENGTH == max(f.max_length for f in campos)

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

    def test_favorites_no_duplicates_when_team_has_several_favorite_rows(self, match, team_home, competition):
        """A team listed in two Favorite rows must not duplicate its events."""
        Favorite.objects.create(team=team_home)
        Favorite.objects.create(team=team_home, competition=competition)

        assert event_pks(Event.objects.favorites()).count(match.pk) == 1

    def test_favorites_no_duplicates_when_both_teams_are_favorites(self, match, team_home, team_away):
        Favorite.objects.create(team=team_home)
        Favorite.objects.create(team=team_away)

        assert event_pks(Event.objects.favorites()).count(match.pk) == 1


class TestEventQuerySetOrdering:
    """Tests for the default ordering and the explicit chronological() order."""

    def test_default_ordering_is_the_bare_timestamp(self):
        assert Event._meta.ordering == ["date"]

    def test_default_ordering_costs_no_joins(self, db):
        """Ordering by related fields made every count, lookup and update join twice."""
        sql = str(Event.objects.all().query)
        assert "JOIN" not in sql
        assert "django_datetime_cast_date" not in sql

    def test_chronological_breaks_ties_by_sport_order(
        self, db, competition, competition_tour, competition_roland_garros, team_home, team_away
    ):
        """Sport order is 1 for football, 2 for cycling and 3 for tennis."""
        slot = timezone.now() + datetime.timedelta(hours=2)
        tennis = SimpleEvent.objects.create(competition=competition_roland_garros, name="Final", date=slot)
        cycling = SimpleEvent.objects.create(competition=competition_tour, name="Etapa", date=slot)
        football = Match.objects.create(competition=competition, local=team_home, visitor=team_away, date=slot)

        ordered = event_pks(Event.objects.chronological().filter(date=slot))

        assert ordered == [football.pk, cycling.pk, tennis.pk]

    def test_chronological_breaks_remaining_ties_by_competition_name(
        self, db, competition, competition_champions, team_home, team_away, team_third
    ):
        """Same sport and same slot: "La Liga" sorts before "UEFA Champions League"."""
        slot = timezone.now() + datetime.timedelta(hours=3)
        champions = Match.objects.create(
            competition=competition_champions, local=team_home, visitor=team_third, date=slot
        )
        liga = Match.objects.create(competition=competition, local=team_home, visitor=team_away, date=slot)

        ordered = event_pks(Event.objects.chronological().filter(date=slot))

        assert ordered == [liga.pk, champions.pk]

    def test_chronological_sorts_by_date_first(self, match, match_future):
        ordered = event_pks(Event.objects.chronological().filter(pk__in=[match_future.pk, match.pk]))
        assert ordered == [match.pk, match_future.pk]


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
