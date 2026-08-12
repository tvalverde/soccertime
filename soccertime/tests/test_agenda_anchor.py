"""Where the agenda opens, and why nothing is hidden to get it there.

`today_onwards()` starts at midnight, so the first thing a visitor read was what had already
happened. Measured on 2026-08-12 at 16:41: of the first 25 rows, **16 had already finished**
and the first live one sat at position 17. On a busy Saturday it is worse — 127 events, of
which roughly 71 are over by 18:00 and 115 by 22:00.

Filtering the past away was measured and rejected. Every event carries `duration = NULL`, so
"finished" is always the flat two-hour default, and 30% of future events are in sports where
that is wrong — a cycling stage runs five hours, golf all day. No cutoff both hides enough and
never hides something live: at 6 hours it still buried two live events at 21:00, and at 2 it
buried five. So the agenda opens at the page holding the present and hides nothing. Being one
page off is harmless; hiding a match that is on is not.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from soccertime.models import Event, Match

PER_PAGE = 25
MADRID = ZoneInfo("Europe/Madrid")


@pytest.fixture
def evening(monkeypatch):
    """Pin the clock to 23:00 today, so "earlier today" has room for a full page.

    `today_onwards()` starts at local midnight, so events placed relative to a real `now`
    land yesterday whenever the suite runs in the morning and are excluded — which is how
    the first draft of these tests failed for a reason that had nothing to do with the
    anchor. Freezing the hour makes the scenario the same whatever time it is run.
    """
    fixed = timezone.localtime(timezone.now(), MADRID).replace(hour=23, minute=0, second=0, microsecond=0)
    monkeypatch.setattr(timezone, "now", lambda: fixed.astimezone(datetime.UTC))
    return fixed


@pytest.fixture
def match_at(db, competition, team_home, team_away, evening):
    def build(offset):
        return Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=timezone.now() + offset,
        )

    return build


def hours(count):
    return datetime.timedelta(hours=count)


def page_of(response):
    return response.context["events"].number


def rows_across_all_pages(client, params=None):
    """Every event the agenda will show, page by page — what "hides nothing" means."""
    first = client.get("/agenda/", params or {}).context["events"]
    seen = []
    for number in first.paginator.page_range:
        page = client.get("/agenda/", {**(params or {}), "page": number}).context["events"]
        seen.extend(event.pk for event in page)
    return seen


@pytest.mark.django_db
class TestTheAgendaOpensAtThePresent:
    def test_it_skips_past_a_full_page_of_finished_events(self, client, match_at):
        """The finding itself: a day whose early hours fill more than one page."""
        for index in range(PER_PAGE + 5):
            match_at(-hours(20) + datetime.timedelta(minutes=index))
        match_at(hours(1))

        assert page_of(client.get("/agenda/")) == 2

    def test_a_short_day_still_opens_on_the_first_page(self, client, match_at):
        match_at(-hours(20))
        match_at(hours(1))

        assert page_of(client.get("/agenda/")) == 1

    def test_an_event_that_started_recently_keeps_the_page_on_it(self, client, match_at):
        """The lookback is why: something that began 30 minutes ago is very likely still on.

        A full page of older events sits behind it, so without the lookback the agenda would
        open past a match in progress.
        """
        for index in range(PER_PAGE):
            match_at(-hours(20) + datetime.timedelta(minutes=index))
        started_recently = match_at(-datetime.timedelta(minutes=30))

        page = client.get("/agenda/").context["events"]

        assert started_recently.pk in {event.pk for event in page}

    def test_an_explicit_page_always_wins(self, client, match_at):
        for index in range(PER_PAGE + 5):
            match_at(-hours(20) + datetime.timedelta(minutes=index))
        match_at(hours(1))

        assert page_of(client.get("/agenda/", {"page": 1})) == 1


@pytest.mark.django_db
class TestItHidesNothing:
    """The assertion that separates this from the filtering approach that was rejected."""

    def test_every_event_is_still_reachable(self, client, match_at):
        expected = {match_at(-hours(20) + datetime.timedelta(minutes=i)).pk for i in range(PER_PAGE + 5)}
        expected.add(match_at(hours(1)).pk)

        assert set(rows_across_all_pages(client)) == expected

    def test_the_total_count_is_untouched(self, client, match_at):
        for index in range(PER_PAGE + 5):
            match_at(-hours(20) + datetime.timedelta(minutes=index))
        match_at(hours(1))

        response = client.get("/agenda/")

        assert response.context["total_events"] == Event.objects.today_onwards().count()


@pytest.mark.django_db
class TestTheAnchorAcrossTheOtherFilters:
    def test_a_requested_date_opens_on_its_first_page(self, client, match_at):
        """Asking for a day is asking for the whole day, from its beginning."""
        for index in range(PER_PAGE + 5):
            match_at(hours(30) + datetime.timedelta(minutes=index))
        requested = timezone.localdate(timezone.now() + hours(30))

        assert page_of(client.get("/agenda/", {"events-date": requested.isoformat()})) == 1

    def test_a_day_entirely_in_the_past_opens_on_its_first_page(self, client, match_at):
        for index in range(PER_PAGE + 5):
            match_at(-hours(30) + datetime.timedelta(minutes=index))
        requested = timezone.localdate(timezone.now() - hours(30))

        assert page_of(client.get("/agenda/", {"events-date": requested.isoformat()})) == 1

    def test_it_anchors_over_what_a_search_leaves(self, client, match_at, team_home):
        for index in range(PER_PAGE + 5):
            match_at(-hours(20) + datetime.timedelta(minutes=index))
        match_at(hours(1))

        assert page_of(client.get("/agenda/", {"search": team_home.name})) == 2

    def test_an_empty_listing_does_not_break(self, client):
        assert page_of(client.get("/agenda/", {"search": "no-existe-nada-asi"})) == 1


@pytest.mark.django_db
class TestTheCost:
    def test_the_anchor_costs_one_query(self, client, match_at, django_assert_num_queries):
        """Counted rather than assumed, on the busiest page of the site.

        Twelve for the whole page here, of which the anchor is exactly one: the same request
        cost eleven before it existed. The absolute number is lower than production's because
        this fixture has no favourite teams or competitions to load — what this pins is that
        the anchor did not quietly become a query per row.
        """
        match_at(hours(1))

        with django_assert_num_queries(12):
            client.get("/agenda/")


@pytest.mark.django_db
class TestTheMarkupCarriesTheInstant:
    """The badge is decided in the browser, so the row has to hand it the start time.

    Server-side would be wrong for up to sixty minutes: every listing is cached for an hour,
    so a rendered badge outlives the event it describes.
    """

    def test_every_row_carries_a_parseable_instant(self, client, match_at):
        event = match_at(hours(1))

        body = client.get("/agenda/").content.decode()

        expected = timezone.localtime(Event.objects.get(pk=event.pk).date).isoformat()
        assert f'data-starts-at="{expected}"' in body

    def test_the_badge_ships_hidden(self, client, match_at):
        """It is revealed by the script; without JavaScript the row reads as it always did."""
        match_at(-datetime.timedelta(minutes=30))

        body = client.get("/agenda/").content.decode()

        assert "live-badge" in body
        assert "d-none" in body
