"""Tests for how the scraper accounts for the rows it does not turn into events."""

import datetime

import pytest
from bs4 import BeautifulSoup

from soccertime.management.commands.scraping.futbolenlatv import ScrapingStats, parse_date_row, parse_iter

BASE_URL = "https://example.com/deporte/automovilismo"

WEEKDAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def header_date():
    """A date the scraper will still accept tomorrow, which a literal one is not.

    `is_valid_date` reads the wall clock — it takes a date from seven days ago to a year
    ahead — so a date typed into a fixture is inside the window on the day it is typed and
    outside it a week later. This one said `21/08/2026`, written on 2026-08-10, and every run
    from 2026-08-29 onwards read it as out of range: the header was dropped, the rows under it
    had no date to sit on, and a test asserting an event came out of them failed for a reason
    that had nothing to do with what it was testing.

    The weekday is decoration — `parse_date_row` splits at `", "` and keeps the tail — but the
    fixture is shaped like the source it stands for, so it is the real one.
    """
    today = datetime.date.today()
    return f"{WEEKDAYS[today.weekday()]}, {today:%d/%m/%Y}"


def page(rows):
    """A results table shaped like the source's: a date header, then event rows."""
    return BeautifulSoup(
        f"""
        <table>
          <tr class="cabeceraTabla"><td>{header_date()}</td></tr>
          <tr class="cabeceraCompericion"><td><a>Fórmula 1</a></td></tr>
          {rows}
        </table>
        """,
        "lxml",
    )


def event_row(time_text, name="G.P. Holanda (Zandvoort) Clasificación"):
    return (
        f"<tr><td>{time_text}</td><td><span>detalle</span></td><td>{name}</td><td><ul><li>DAZN F1</li></ul></td></tr>"
    )


def test_the_fixture_carries_a_date_the_scraper_accepts():
    """Guards every test below, which read a page this builds.

    A header out of range is dropped, and the rows under it lose the date they sit on — so
    these tests stop testing what they say they test and start reporting the calendar.

    It reads the header out of `page()` rather than building one of its own, because the
    literal that expired lived in that template and a guard aimed anywhere else would have
    watched it go stale. What this catches on the spot is a date already outside the window;
    a literal typed in today still has its week, but it fails here, naming the fixture, rather
    than in four tests that appear to be about counting events.
    """
    header = page("").select_one("tr.cabeceraTabla")

    assert header is not None, "the fixture no longer has a date header for the rows to sit on"
    assert parse_date_row(header, "Automovilismo", BASE_URL) is not None, (
        f"{header.get_text(strip=True)!r} is outside the window is_valid_date allows"
    )


class TestPendingTime:
    """ "PD" — por determinar — means the time is not announced, not that the row is bad."""

    def test_is_counted_apart_from_the_malformed_rows(self):
        stats = ScrapingStats()

        list(parse_iter(page(event_row("PD")), "Automovilismo", BASE_URL, stats))

        assert stats.pending_time == 1
        assert stats.skipped == 0, "it is a real event, not a row that could not be read"
        assert stats.errors == 0

    def test_the_event_is_still_not_produced(self):
        """An entry with no time has nowhere to sit in a listing ordered by time."""
        events = list(parse_iter(page(event_row("PD")), "Automovilismo", BASE_URL, ScrapingStats()))

        assert events == []

    def test_it_says_which_event_it_was(self, caplog):
        """These were the only discarded rows raising no warning, so they went unnoticed."""
        with caplog.at_level("INFO"):
            list(parse_iter(page(event_row("PD")), "Automovilismo", BASE_URL, ScrapingStats()))

        assert "G.P. Holanda (Zandvoort) Clasificación" in caplog.text

    def test_a_dated_event_alongside_one_pending_is_still_produced(self):
        stats = ScrapingStats()

        events = list(
            parse_iter(page(event_row("PD") + event_row("14:30", "Carrera")), "Automovilismo", BASE_URL, stats)
        )

        assert len(events) == 1
        assert stats.processed == 1
        assert stats.pending_time == 1


class TestStatsAggregation:
    def test_folding_a_page_into_the_totals_carries_every_counter(self):
        totals, page_stats = ScrapingStats(), ScrapingStats()
        page_stats.processed, page_stats.skipped, page_stats.errors, page_stats.pending_time = 5, 2, 1, 3

        totals.add(page_stats)
        totals.add(page_stats)

        assert (totals.processed, totals.skipped, totals.errors, totals.pending_time) == (10, 4, 2, 6)

    def test_the_summary_names_the_pending_ones(self):
        """The count is the whole point: it is what makes them visible in the log."""
        stats = ScrapingStats()
        stats.pending_time = 42

        assert "pending_time=42" in str(stats)


@pytest.mark.parametrize("time_text", ["", "   ", "??", "25:99", "pd"])
def test_a_time_that_is_neither_valid_nor_the_marker_is_not_pending(time_text):
    """Anything else unreadable stays an error; the marker is matched exactly."""
    stats = ScrapingStats()

    list(parse_iter(page(event_row(time_text)), "Automovilismo", BASE_URL, stats))

    assert stats.pending_time == 0


@pytest.mark.parametrize("time_text", ["PD", " PD ", "PD\n"])
def test_whitespace_around_the_marker_does_not_hide_it(time_text):
    """The cell text is stripped before comparison, so padding is harmless."""
    stats = ScrapingStats()

    list(parse_iter(page(event_row(time_text)), "Automovilismo", BASE_URL, stats))

    assert stats.pending_time == 1
