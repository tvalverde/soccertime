"""What the agenda prints as the time of an event, and which clock it comes from.

Nothing in the suite asserted a rendered time, which is how the templates came to read
`{{ event.date.time|date:'H:i' }}`. `.time` returns a naive `datetime.time`, so the value
reaches the formatter with its zone already discarded and no conversion can touch it. The
display was therefore deaf to `TIME_ZONE` — proved by rendering the same instant under two
settings and getting the same string — which is exactly the state in which the stored data
can be moved to real UTC and every time on the site silently shifts.

These pin the contract instead: **the agenda prints an event in the site's own timezone.**
That holds while the times are stored as Spanish wall clock labelled UTC, and it goes on
holding once they are real UTC read back in `Europe/Madrid`, which is what makes them the
proof that the migration moved the data without moving the page.

Every event is read back from the database before being rendered. Writing the assertion
against the instance just created passes for the wrong reason: that object still carries the
timezone it was built with, where a view only ever sees what Django stored.
"""

import datetime
import re
from zoneinfo import ZoneInfo

import pytest
from django.template.loader import render_to_string
from django.test import override_settings
from django.utils import timezone

from soccertime.models import Match

MADRID = ZoneInfo("Europe/Madrid")

# Chosen either side of the last Sunday in March: 22:00 is 20:00 UTC in June and 21:00 UTC in
# December. A test written against one season only would go green while the other was an hour
# out, and the catalogue is split 55/45 between them.
SUMMER = datetime.datetime(2026, 6, 15, 22, 0, tzinfo=MADRID)
WINTER = datetime.datetime(2026, 12, 20, 22, 0, tzinfo=MADRID)


def time_cell(event):
    """The clock the agenda actually prints, not merely a substring of the whole row.

    The time is read out of its cell rather than the cell being compared whole: the same
    `<th>` also carries the live badge, which `live_state.js` reveals in the browser, and
    this test is about the clock.
    """
    rendered = render_to_string("soccertime/agenda_item.html", {"event": event, "parent_event": event})
    cell = re.search(r'<th scope="row">(.*?)</th>', rendered, re.S).group(1)
    return re.search(r"\d{2}:\d{2}", cell).group(0)


def day_header(event):
    return render_to_string("soccertime/agenda_header.html", {"event": event})


@pytest.fixture
def match_at(db, competition, team_home, team_away):
    """A match at a chosen instant, read back as a view would see it."""

    def build(moment):
        match = Match.objects.create(competition=competition, local=team_home, visitor=team_away, date=moment)
        return Match.objects.get(pk=match.pk)

    return build


class TestTheDisplayedTime:
    def test_the_agenda_prints_the_event_in_the_sites_own_timezone(self, match_at):
        """The invariant that survives the migration, which is why it is worth pinning.

        Deliberately expressed against `localtime` rather than a literal: today that is the
        stored value read in UTC, and after the migration it is the same instant read in
        Madrid. One assertion, both worlds, and it fails the moment the page starts printing
        a clock nobody configured.
        """
        event = match_at(timezone.now() + datetime.timedelta(hours=5))

        assert time_cell(event) == timezone.localtime(event.date).strftime("%H:%M")

    @override_settings(TIME_ZONE="Europe/Madrid")
    def test_the_time_follows_the_configured_timezone_in_summer(self, match_at):
        """The one with teeth: this fails while the template calls `.time`.

        22:00 in Madrid in June is 20:00 UTC. With the zone thrown away the page prints
        20:00 — the two-hour shift the migration would otherwise have caused, reproduced
        without touching a single row of production data.
        """
        timezone.activate(MADRID)

        assert time_cell(match_at(SUMMER)) == "22:00"

    @override_settings(TIME_ZONE="Europe/Madrid")
    def test_the_time_follows_the_configured_timezone_in_winter(self, match_at):
        """Winter is one hour, not two, so a constant offset passes summer and fails here."""
        timezone.activate(MADRID)

        assert time_cell(match_at(WINTER)) == "22:00"


class TestTheDayHeader:
    @override_settings(TIME_ZONE="Europe/Madrid")
    def test_an_event_just_after_midnight_is_filed_under_its_own_day(self, match_at):
        """The header groups by day, and `.date` discarded the zone the same way.

        00:30 in Madrid is 22:30 UTC of the day before, so reading the stored date raw files
        1,737 of the 52,133 events — every one between midnight and one in the morning —
        under the previous day.
        """
        timezone.activate(MADRID)
        event = match_at(datetime.datetime(2026, 6, 15, 0, 30, tzinfo=MADRID))

        header = day_header(event)

        assert "15" in header
        assert "14" not in header

    def test_the_header_names_the_day_the_site_would_call_it(self, match_at):
        """The neutral half of the pair, true before and after the migration."""
        event = match_at(timezone.now() + datetime.timedelta(days=4))

        assert timezone.localtime(event.date).strftime("%d") in day_header(event)
