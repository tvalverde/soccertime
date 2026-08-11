"""The conversion that moves stored event times from Spanish wall clock to real UTC.

The scraper called `make_aware(value, get_current_timezone())` with `TIME_ZONE = "UTC"`, which
applies no offset at all. A match kicking off at 22:00 Spanish time was stored as `22:00 UTC`
— the right number with the wrong label. Rendering it in UTC printed 22:00, so the site looked
correct, and every comparison against `timezone.now()` was out by the offset.

The offset is not a constant. It has to come from `Europe/Madrid` applied to **each event's
own date**, because the scraper writes events months ahead and routinely crosses a changeover:
28,689 production rows fall in summer time and 23,444 in winter, a 55/45 split, so a single
subtraction would put nearly half the catalogue an hour out. That is what these test.

The conversion itself lives in `convert_stored_dates` rather than inside the migration, so it
can be tested directly; the migration is a two-line call in each direction.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from soccertime.event_dates import convert_stored_dates
from soccertime.management.commands.scrapit import SPANISH_SCREEN_TIME
from soccertime.models import Event, Match

MADRID = ZoneInfo("Europe/Madrid")


@pytest.fixture
def stored_as_scraped(db, competition, team_home, team_away):
    """A row written the way the old scraper wrote them: Spanish wall clock, labelled UTC."""

    def build(year, month, day, hour, minute=0):
        return Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.UTC),
        )

    return build


def stored_date(event):
    return Event.objects.values_list("date", flat=True).get(pk=event.pk)


class TestForwards:
    def test_a_summer_event_moves_back_two_hours(self, stored_as_scraped):
        """22:00 Spanish time in June is 20:00 UTC."""
        event = stored_as_scraped(2026, 6, 15, 22)

        convert_stored_dates(Event, to_utc=True)

        assert stored_date(event) == datetime.datetime(2026, 6, 15, 20, 0, tzinfo=datetime.UTC)

    def test_a_winter_event_moves_back_one_hour(self, stored_as_scraped):
        """The half the catalogue a constant offset would ruin: December is +1, not +2."""
        event = stored_as_scraped(2026, 12, 20, 22)

        convert_stored_dates(Event, to_utc=True)

        assert stored_date(event) == datetime.datetime(2026, 12, 20, 21, 0, tzinfo=datetime.UTC)

    def test_both_seasons_convert_correctly_in_one_pass(self, stored_as_scraped):
        """The migration runs once over rows on both sides of the changeover.

        Grouping by offset is an optimisation; getting the grouping wrong would show up
        exactly here and nowhere else, since either test above passes on its own.
        """
        summer = stored_as_scraped(2026, 6, 15, 22)
        winter = stored_as_scraped(2026, 12, 20, 22)

        convert_stored_dates(Event, to_utc=True)

        assert stored_date(summer).hour == 20
        assert stored_date(winter).hour == 21

    def test_the_displayed_time_does_not_move(self, stored_as_scraped, settings):
        """The whole point, stated as an assertion: the data moves and the page does not."""
        event = stored_as_scraped(2026, 6, 15, 22)
        settings.TIME_ZONE = "Europe/Madrid"
        timezone.activate(MADRID)

        convert_stored_dates(Event, to_utc=True)

        assert timezone.localtime(stored_date(event)).strftime("%H:%M") == "22:00"

    def test_an_ambiguous_hour_resolves_to_the_first_pass(self, stored_as_scraped):
        """October's repeated hour, six rows in production.

        02:30 happens twice on the night the clocks go back. It is read as the first pass,
        CEST, which is what a schedule published weeks in advance means — and which is also
        what Django's `make_aware` does, so the scraper and this agree without being made to.
        """
        event = stored_as_scraped(2026, 10, 25, 2, 30)

        convert_stored_dates(Event, to_utc=True)

        assert stored_date(event) == datetime.datetime(2026, 10, 25, 0, 30, tzinfo=datetime.UTC)


class TestBackwards:
    @pytest.mark.parametrize(
        "moment", [(2026, 6, 15, 22), (2026, 12, 20, 22), (2026, 10, 25, 2)], ids=["summer", "winter", "ambiguous"]
    )
    def test_the_reverse_restores_the_original(self, stored_as_scraped, moment):
        """A migration whose inverse is wrong is a migration you cannot roll back.

        The recovery path for this change is `migrate` backwards, not a restore from the
        snapshot, so the inverse has to be exact.
        """
        event = stored_as_scraped(*moment)
        original = stored_date(event)

        convert_stored_dates(Event, to_utc=True)
        convert_stored_dates(Event, to_utc=False)

        assert stored_date(event) == original


class TestItTouchesNothingElse:
    def test_it_builds_no_model_instances(self, stored_as_scraped, django_assert_max_num_queries):
        """Data migrations run against historical models, which can still carry field options
        a later migration removes — an `ImageField` declaring `width_field` would read the file
        on `post_init`. Reading with `values_list` and writing with `update` means no instance,
        and therefore no signal handler, is ever built.

        Two rows on the same side of the changeover cost one read and one update, not one
        update per row.
        """
        stored_as_scraped(2026, 6, 15, 22)
        stored_as_scraped(2026, 6, 16, 18)

        with django_assert_max_num_queries(2):
            convert_stored_dates(Event, to_utc=True)


class TestTheScraperWritesRealUtc:
    """The other half of the same mistake, and the one that would undo the migration.

    `upsert_event` matches on a two-day window rather than an exact date, so a scraper left on
    the old labelling could not duplicate the catalogue — it would do something quieter and
    worse, realigning every upcoming event back onto the wall clock with nothing to show for
    it. That is why the scraper, the setting and the migration are one deploy.
    """

    @pytest.mark.parametrize(
        ("announced", "expected_utc_hour"),
        [(datetime.datetime(2026, 6, 15, 22, 0), 20), (datetime.datetime(2026, 12, 20, 22, 0), 21)],
        ids=["summer", "winter"],
    )
    def test_it_reads_the_announced_time_as_spanish_screen_time(self, announced, expected_utc_hour):
        """Both are resolved in the same call, from the event's date and not from today's.

        A scrape running in August writes fixtures for November all the time; taking the
        offset from the moment the process runs would put every one of them an hour out.
        """
        stored = timezone.make_aware(announced, timezone=SPANISH_SCREEN_TIME)

        assert stored.astimezone(datetime.UTC).hour == expected_utc_hour
        assert timezone.localtime(stored, MADRID).strftime("%H:%M") == "22:00"
