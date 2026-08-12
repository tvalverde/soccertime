"""Exact event identity, and the reconciliation that replaced the ±2-day window.

`upsert_event` used to treat any event of the same (competition, local, visitor) within two
days as the same event and realign it, so a second fixture of the same pairing could not be
stored: an ACB doubleheader on the same court, an NBA back-to-back. 219 such pairs exist in
rows written before the window landed; zero could exist after it. No smaller window helps —
99 of those 219 pairs sit under three hours apart — and the source offers no round number or
stable id to tell the cases apart. Closeness is ambiguous by nature: the same shape is
sometimes a duplicate and sometimes two real games, and only what the source lists *today*
can say which.

So identity is exact, and date changes are observed rather than guessed: each scrape unit
covers a knowable scope, what it covered and did not list is what moved or was cancelled.
A move brings its replacement in the same scrape (seen >= previously stored, prune at once);
anything else is ambiguous — an omission or a cancellation — and falls only after two
consecutive misses, evidence-based rather than time-based, so the rule survives a change of
scrape frequency.
"""

import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.utils import timezone

from soccertime.management.commands.scraping.base import (
    Event as AgendaEvent,
)
from soccertime.management.commands.scraping.base import (
    EventDetails,
    MatchDetails,
    ScrapeUnit,
)
from soccertime.models import Event, Match, Race, SimpleEvent, Team

MADRID = ZoneInfo("Europe/Madrid")


def announced(days_ahead, hour, minute=0):
    """A naive Spanish-wall-clock datetime, the shape the parser hands over."""
    base = timezone.localtime(timezone.now(), MADRID) + datetime.timedelta(days=days_ahead)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=None)


def stored_instant(naive):
    """Where that announcement lands in the database."""
    return timezone.make_aware(naive, timezone=MADRID)


def match_event(local, visitor, when, competition="Liga ACB", sport="Baloncesto"):
    return AgendaEvent(
        datetime=when,
        sport=sport,
        competition=competition,
        details=MatchDetails(local=local, visitor=visitor),
        channels=["Canal por confirmar"],
    )


def scrape(*units):
    with patch(
        "soccertime.management.commands.scraping.example.ExampleSource.iter_units",
        return_value=iter(units),
    ):
        call_command("scrapit", "--source=example", "--include-disabled")


def sport_unit(*events, sport="Baloncesto"):
    return ScrapeUnit(events=list(events), sport=sport)


def future_matches():
    return {
        (m.local.name, m.visitor.name, timezone.localtime(m.date).strftime("%d %H:%M"))
        for m in Match.objects.filter(date__gte=timezone.now())
    }


@pytest.mark.django_db
class TestExactIdentity:
    def test_a_doubleheader_on_the_same_court_is_two_events(self):
        """The finding itself: two real games two hours apart, same pairing, same venue.

        The window made this impossible to store — the second game realigned the first.
        """
        first = announced(3, 18)
        second = announced(3, 20)

        scrape(sport_unit(match_event("Baskonia", "Madrid", first), match_event("Baskonia", "Madrid", second)))

        assert Match.objects.count() == 2

    def test_a_back_to_back_on_consecutive_days_is_two_events(self):
        scrape(
            sport_unit(
                match_event("Nets", "Magic", announced(3, 20), competition="NBA"),
                match_event("Nets", "Magic", announced(4, 20), competition="NBA"),
            )
        )

        assert Match.objects.count() == 2

    def test_scraping_the_same_listing_twice_stores_it_once(self):
        """Idempotence, which the exact identity must give for free."""
        when = announced(3, 20)

        scrape(sport_unit(match_event("Baskonia", "Madrid", when)))
        scrape(sport_unit(match_event("Baskonia", "Madrid", when)))

        assert Match.objects.count() == 1


@pytest.mark.django_db
class TestMovesArePrunedAtOnce:
    def test_a_moved_event_is_replaced_in_a_single_scrape(self):
        """The window's original purpose, kept: the source shifts a fixture, not announces two.

        The move brings its replacement in the same scrape — seen >= previously stored —
        so the stale row goes immediately, whatever the scrape frequency.
        """
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18))))

        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 20))))

        assert Match.objects.count() == 1
        assert timezone.localtime(Match.objects.get().date).hour == 20

    def test_a_move_across_days_is_also_one_scrape(self):
        """The case the old window caught only within ±2 days, now unbounded."""
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(2, 20))))

        scrape(
            sport_unit(
                match_event("Baskonia", "Madrid", announced(6, 20)),
                # A second event keeps the covered range wide enough to include day 2.
                match_event("Unicaja", "Valencia", announced(2, 19)),
            )
        )

        pairings = future_matches()
        assert ("Baskonia", "Madrid", timezone.localtime(stored_instant(announced(6, 20))).strftime("%d %H:%M")) in pairings
        assert len([p for p in pairings if p[0] == "Baskonia"]) == 1

    def test_one_game_of_a_doubleheader_can_move(self):
        """Stored {Sat, Sun}, seen {Sat, Mon}: the Sun row is superseded, not the pair."""
        scrape(
            sport_unit(
                match_event("Baskonia", "Madrid", announced(3, 18)),
                match_event("Baskonia", "Madrid", announced(4, 18)),
            )
        )

        scrape(
            sport_unit(
                match_event("Baskonia", "Madrid", announced(3, 18)),
                match_event("Baskonia", "Madrid", announced(5, 18)),
            )
        )

        days = sorted(timezone.localtime(m.date).day for m in Match.objects.all())
        assert len(days) == 2
        assert timezone.localtime(stored_instant(announced(4, 18))).day not in days


@pytest.mark.django_db
class TestAmbiguityWaitsForEvidence:
    def test_an_omitted_row_survives_one_miss(self):
        """A doubleheader with one row dropped by the source must not flicker.

        Stored 2, seen 1: ambiguous, so the unseen row is marked, not removed — with the
        hour-long page cache a flicker would be user-visible.
        """
        scrape(
            sport_unit(
                match_event("Baskonia", "Madrid", announced(3, 18)),
                match_event("Baskonia", "Madrid", announced(3, 20)),
            )
        )

        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18))))

        assert Match.objects.count() == 2
        assert Event.objects.filter(missing_scrapes=1).count() == 1

    def test_the_second_consecutive_miss_removes_it(self):
        """Two successful scrapes without the row is the evidence a cancellation leaves."""
        scrape(
            sport_unit(
                match_event("Baskonia", "Madrid", announced(3, 18)),
                match_event("Baskonia", "Madrid", announced(3, 20)),
            )
        )

        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18))))
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18))))

        assert Match.objects.count() == 1

    def test_reappearing_resets_the_count(self):
        scrape(
            sport_unit(
                match_event("Baskonia", "Madrid", announced(3, 18)),
                match_event("Baskonia", "Madrid", announced(3, 20)),
            )
        )
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18))))

        scrape(
            sport_unit(
                match_event("Baskonia", "Madrid", announced(3, 18)),
                match_event("Baskonia", "Madrid", announced(3, 20)),
            )
        )

        assert Match.objects.count() == 2
        assert Event.objects.filter(missing_scrapes__gt=0).count() == 0


@pytest.mark.django_db
class TestTheScopeOfAUnit:
    def test_a_unit_that_yields_nothing_touches_nothing(self):
        """An empty or broken page is indistinguishable from a day without sport."""
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18))))

        scrape(ScrapeUnit(events=[], sport="Baloncesto"))
        scrape(ScrapeUnit(events=[], sport="Baloncesto"))

        assert Match.objects.count() == 1
        assert Event.objects.filter(missing_scrapes__gt=0).count() == 0

    def test_an_incomplete_unit_stores_but_never_prunes(self):
        """A page that died mid-parse is a partial view; acting on it would prune real rows."""
        scrape(
            sport_unit(
                match_event("Baskonia", "Madrid", announced(3, 18)),
                match_event("Baskonia", "Madrid", announced(3, 20)),
            )
        )

        scrape(ScrapeUnit(events=[match_event("Unicaja", "Valencia", announced(3, 19))], sport="Baloncesto", complete=False))
        scrape(ScrapeUnit(events=[match_event("Unicaja", "Valencia", announced(3, 19))], sport="Baloncesto", complete=False))

        assert Match.objects.count() == 3
        assert Event.objects.filter(missing_scrapes__gt=0).count() == 0

    def test_another_sport_is_out_of_scope(self):
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18))))

        scrape(sport_unit(match_event("Alaves", "Getafe", announced(3, 18), competition="LaLiga", sport="Fútbol"), sport="Fútbol"))
        scrape(sport_unit(match_event("Alaves", "Getafe", announced(3, 18), competition="LaLiga", sport="Fútbol"), sport="Fútbol"))

        assert Match.objects.filter(local__name="Baskonia").count() == 1

    def test_days_beyond_the_covered_range_are_out_of_scope(self):
        """Fixtures far out live on team pages; an agenda page must not judge them."""
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(20, 18))))

        scrape(sport_unit(match_event("Unicaja", "Valencia", announced(2, 19))))
        scrape(sport_unit(match_event("Unicaja", "Valencia", announced(2, 19))))

        assert Match.objects.filter(local__name="Baskonia").count() == 1

    def test_past_events_are_history_and_never_pruned(self):
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(1, 18))))
        Event.objects.update(date=timezone.now() - datetime.timedelta(days=1))

        scrape(sport_unit(match_event("Unicaja", "Valencia", announced(1, 19))))
        scrape(sport_unit(match_event("Unicaja", "Valencia", announced(1, 19))))

        assert Match.objects.filter(local__name="Baskonia").count() == 1

    def test_a_team_unit_only_judges_that_teams_matches(self):
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18))))
        Team.objects.filter(name="Baskonia").update(futbolenlatv_slug="baskonia")
        scrape(
            sport_unit(
                match_event("Alaves", "Getafe", announced(3, 18), competition="LaLiga", sport="Fútbol"),
                sport="Fútbol",
            )
        )

        # The Baskonia team page no longer lists the day-3 match but does list another.
        unit = ScrapeUnit(
            events=[match_event("Baskonia", "Getafe", announced(3, 20), competition="Amistoso", sport="Fútbol")],
            team_slug="baskonia",
        )
        scrape(unit)

        # Seen >= previously stored for the (Baskonia, Madrid) pairing does not hold — the
        # new match is another pairing — so the old row is marked, and Alaves is untouched.
        assert Match.objects.filter(local__name="Alaves").count() == 1
        assert Event.objects.filter(missing_scrapes__gt=0).count() == 1


@pytest.mark.django_db
class TestSeenBookkeeping:
    def test_every_seen_event_is_stamped(self):
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18))))

        event = Event.objects.get()
        assert event.last_seen_at is not None
        assert event.missing_scrapes == 0

    def test_a_unit_without_scope_stamps_but_never_prunes(self):
        """The default for a source that has not declared units — the example source."""
        scrape(sport_unit(match_event("Baskonia", "Madrid", announced(3, 18)), sport=None))
        scrape(ScrapeUnit(events=[match_event("Unicaja", "Valencia", announced(3, 19))]))
        scrape(ScrapeUnit(events=[match_event("Unicaja", "Valencia", announced(3, 19))]))

        assert Match.objects.filter(local__name="Baskonia").count() == 1


def simple_event(name, when, details=None, competition="Vuelta a España", sport="Ciclismo"):
    return AgendaEvent(
        datetime=when,
        sport=sport,
        competition=competition,
        details=EventDetails(name=name, details=details),
        channels=["Teledeporte"],
    )


@pytest.mark.django_db
class TestDetailsAreDataNotIdentity:
    """The phase text is something the source rephrases, and it sat inside the identity.

    Every rephrasing created a duplicate row: 234 existed in production when this was
    found — two `Etapa 1` rows at the same instant differing only in that text.
    """

    def test_a_rephrased_detail_updates_the_row_instead_of_duplicating_it(self):
        when = announced(3, 14, 30)

        scrape(sport_unit(simple_event("Etapa 1", when, details="1ª Etapa"), sport="Ciclismo"))
        scrape(sport_unit(simple_event("Etapa 1", when, details="Etapa llana"), sport="Ciclismo"))

        assert SimpleEvent.objects.count() == 1
        assert SimpleEvent.objects.get().details == "Etapa llana"

    def test_legacy_twins_in_the_same_slot_are_healed_in_one_scrape(self):
        """Rows already duplicated by the old identity share (competition, name, instant).

        An unseen row whose exact slot a seen row occupies is a duplicate by definition —
        no counting, no grace. 234 such rows existed in production.
        """
        when = announced(3, 14, 30)
        scrape(sport_unit(simple_event("Etapa 1", when, details="texto nuevo"), sport="Ciclismo"))
        original = SimpleEvent.objects.get()
        SimpleEvent.objects.create(
            competition=original.competition,
            name="Etapa 1",
            date=original.date,
            details="texto de otra época",
        )
        assert SimpleEvent.objects.count() == 2

        scrape(sport_unit(simple_event("Etapa 1", when, details="texto nuevo"), sport="Ciclismo"))

        assert SimpleEvent.objects.count() == 1

    def test_a_stage_stored_under_another_concrete_type_is_superseded(self):
        """One vintage of the parser stored stages as Race, another as SimpleEvent.

        The pairing is the identity, not the Python class it landed in: the seen row
        supersedes the unseen one across types.
        """
        when = announced(3, 14, 30)
        # La fila heredada, como la almacenó el parser antiguo: una Race.

        from soccertime.models import Competition, Sport
        sport_obj, _ = Sport.objects.get_or_create(name="Ciclismo")
        comp, _ = Competition.objects.get_or_create(name="Vuelta a España", sport=sport_obj)
        Race.objects.create(competition=comp, name="Etapa 1", date=stored_instant(when))

        scrape(sport_unit(simple_event("Etapa 1", when), sport="Ciclismo"))

        assert Race.objects.count() == 0
        assert SimpleEvent.objects.count() == 1
