"""Comparisons between stored event times and the present moment.

The scraper stored Spanish wall-clock times labelled UTC. Rendering them in UTC cancelled the
error, so the page was right; nothing that compared them against `timezone.now()` was, because
`now()` is genuine UTC and the stored values ran two hours ahead of themselves in summer and
one in winter. Measured on production before the fix: the front page held 111 events and 7 of
them had already finished, because `in_window(hours_before=3)` retained events for five real
hours in summer and four in winter — never the three it declares.

Two separate defects live here and only one of them is fixed by moving the data:

- The plain `now()` comparisons become correct the moment the stored values mean what they
  say. They need no code change, which is the argument for migrating rather than patching.
- The `now().date()` family is wrong under **either** scheme, because it takes the UTC date
  and the UTC midnight. Between midnight and 02:00 in Madrid that is still yesterday.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from soccertime.models import Event, Match

MADRID = ZoneInfo("Europe/Madrid")


@pytest.fixture(autouse=True)
def spanish_time(settings):
    """Every assertion here is about Spanish local time, so pin it for the whole module."""
    settings.TIME_ZONE = "Europe/Madrid"
    timezone.activate(MADRID)
    yield
    timezone.deactivate()


@pytest.fixture
def match_at(db, competition, team_home, team_away):
    def build(moment):
        return Match.objects.create(competition=competition, local=team_home, visitor=team_away, date=moment)

    return build


class TestTheWindowMeasuresRealHours:
    """`hours_before=3` must mean three hours, whatever the season."""

    def test_it_keeps_an_event_that_started_two_hours_ago(self, match_at):
        event = match_at(timezone.now() - datetime.timedelta(hours=2))

        assert event.pk in set(Event.objects.in_window().values_list("pk", flat=True))

    def test_it_drops_an_event_that_started_four_hours_ago(self, match_at):
        """Pins the semantics, and passes today — which is the point worth being clear about.

        These three write their events at true instants, so they were never the thing that was
        broken. The defect lived in the *data*: rows the scraper wrote as Spanish wall clock
        labelled UTC looked two hours younger than they were, so an event four real hours old
        read as two and stayed on the front page. The test that demonstrates that is in
        `test_event_dates_migration.py`, which writes a row the old way and asserts where it
        lands. This one guards the meaning of `hours_before` from here on.
        """
        event = match_at(timezone.now() - datetime.timedelta(hours=4))

        assert event.pk not in set(Event.objects.in_window().values_list("pk", flat=True))

    def test_it_keeps_an_event_starting_soon(self, match_at):
        event = match_at(timezone.now() + datetime.timedelta(hours=6))

        assert event.pk in set(Event.objects.in_window().values_list("pk", flat=True))


class TestTodayMeansTheSpanishToday:
    """Midnight and "today" have to be Spanish, not UTC.

    `today_onwards` built midnight with `timezone.now().replace(hour=0, ...)`, which is
    midnight **UTC** — 02:00 in Madrid. For the two hours after midnight the site's idea of
    today was still yesterday, so an event at 00:30 was excluded from a listing that claims to
    start at the beginning of today.
    """

    def test_an_event_just_after_midnight_counts_as_today(self, match_at):
        madrid_now = timezone.localtime(timezone.now())
        just_after_midnight = madrid_now.replace(hour=0, minute=30, second=0, microsecond=0)
        event = match_at(just_after_midnight)

        assert event.pk in set(Event.objects.today_onwards().values_list("pk", flat=True))

    def test_yesterdays_events_are_still_excluded(self, match_at):
        """Guards the test above: a filter that let everything through would also pass it."""
        madrid_now = timezone.localtime(timezone.now())
        yesterday = madrid_now.replace(hour=12, minute=0) - datetime.timedelta(days=1)
        event = match_at(yesterday)

        assert event.pk not in set(Event.objects.today_onwards().values_list("pk", flat=True))
