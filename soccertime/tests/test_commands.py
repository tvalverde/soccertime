"""
Tests for management commands.

These are integration tests that test the scrapit command and scraping sources.
"""

import datetime
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command

from soccertime.management.commands.scraping.base import (
    Event as ScrapingEvent,
)
from soccertime.management.commands.scraping.base import (
    EventDetails,
    MatchDetails,
    RaceDetails,
    get_available_sources,
    list_source_names,
)
from soccertime.models import (
    Channel,
    Competition,
    Event,
    Match,
    Race,
    SimpleEvent,
    Sport,
    Team,
)


class TestScrapitCommandBasic:
    """Basic tests for scrapit command."""

    def test_list_sources(self, db):
        """Should list available sources."""
        out = StringIO()
        call_command("scrapit", "--list-sources", stdout=out)
        output = out.getvalue()
        assert "futbolenlatv" in output

    def test_dry_run_does_not_save(self, db):
        """Dry run should not create any database records."""
        initial_count = Event.objects.count()
        out = StringIO()
        call_command("scrapit", "--dry-run", "--source=futbolenlatv", stdout=out)
        assert Event.objects.count() == initial_count

    def test_unknown_source_raises_error(self, db):
        """Should raise error for unknown source."""
        with pytest.raises(Exception) as exc_info:
            call_command("scrapit", "--source=nonexistent")
        assert "Unknown source" in str(exc_info.value)


class TestScrapitCommandProcessing:
    """Tests for scrapit command event processing logic.

    These tests use the 'example' source with mocked data to test
    the event processing pipeline without making real HTTP requests.
    """

    @pytest.fixture
    def mock_match_event(self):
        """Create a mock match event."""
        return ScrapingEvent(
            datetime=datetime.datetime.now() + datetime.timedelta(hours=2),
            sport="Futbol Test",
            competition="Test League",
            competition_crest=None,
            channels=["Test Channel"],
            details=MatchDetails(
                local="Test Home Team",
                local_crest=None,
                visitor="Test Away Team",
                visitor_crest=None,
                details="Test match details",
            ),
        )

    @pytest.fixture
    def mock_race_event(self):
        """Create a mock race event."""
        return ScrapingEvent(
            datetime=datetime.datetime.now() + datetime.timedelta(hours=3),
            sport="Ciclismo Test",
            competition="Test Tour",
            competition_crest=None,
            channels=["Test Channel 2"],
            details=RaceDetails(
                name="Stage 1",
                details="Mountain stage",
            ),
        )

    @pytest.fixture
    def mock_simple_event(self):
        """Create a mock simple event."""
        return ScrapingEvent(
            datetime=datetime.datetime.now() + datetime.timedelta(hours=4),
            sport="Tenis Test",
            competition="Test Open",
            competition_crest=None,
            channels=["Test Channel 3"],
            details=EventDetails(
                name="Final Match",
                details="Singles final",
            ),
        )

    def test_creates_sport_from_event(self, db, mock_match_event):
        """Should create sport when processing event."""
        with (
            patch("soccertime.management.commands.scraping.example.ExampleSource.get_events") as mock_get,
            patch("soccertime.management.commands.scrapit.requests.get") as mock_requests,
        ):
            mock_get.return_value = iter([mock_match_event])
            mock_requests.return_value.status_code = 404  # Simulate no image
            call_command("scrapit", "--source=example", "--include-disabled")

        assert Sport.objects.filter(name="Futbol Test").exists()

    def test_creates_competition_from_event(self, db, mock_match_event):
        """Should create competition when processing event."""
        with (
            patch("soccertime.management.commands.scraping.example.ExampleSource.get_events") as mock_get,
            patch("soccertime.management.commands.scrapit.requests.get") as mock_requests,
        ):
            mock_get.return_value = iter([mock_match_event])
            mock_requests.return_value.status_code = 404
            call_command("scrapit", "--source=example", "--include-disabled")

        assert Competition.objects.filter(name="Test League").exists()

    def test_creates_teams_from_match(self, db, mock_match_event):
        """Should create teams when processing match event."""
        with (
            patch("soccertime.management.commands.scraping.example.ExampleSource.get_events") as mock_get,
            patch("soccertime.management.commands.scrapit.requests.get") as mock_requests,
        ):
            mock_get.return_value = iter([mock_match_event])
            mock_requests.return_value.status_code = 404
            call_command("scrapit", "--source=example", "--include-disabled")

        assert Team.objects.filter(name="Test Home Team").exists()
        assert Team.objects.filter(name="Test Away Team").exists()

    def test_creates_match_event(self, db, mock_match_event):
        """Should create match event."""
        with (
            patch("soccertime.management.commands.scraping.example.ExampleSource.get_events") as mock_get,
            patch("soccertime.management.commands.scrapit.requests.get") as mock_requests,
        ):
            mock_get.return_value = iter([mock_match_event])
            mock_requests.return_value.status_code = 404
            call_command("scrapit", "--source=example", "--include-disabled")

        match = Match.objects.filter(
            local__name="Test Home Team",
            visitor__name="Test Away Team",
        ).first()
        assert match is not None
        assert match.event_type == Event.EventType.MATCH

    def test_creates_race_event(self, db, mock_race_event):
        """Should create race event."""
        with patch("soccertime.management.commands.scraping.example.ExampleSource.get_events") as mock_get:
            mock_get.return_value = iter([mock_race_event])
            call_command("scrapit", "--source=example", "--include-disabled")

        race = Race.objects.filter(name="Stage 1").first()
        assert race is not None
        assert race.event_type == Event.EventType.RACE

    def test_creates_simple_event(self, db, mock_simple_event):
        """Should create simple event."""
        with patch("soccertime.management.commands.scraping.example.ExampleSource.get_events") as mock_get:
            mock_get.return_value = iter([mock_simple_event])
            call_command("scrapit", "--source=example", "--include-disabled")

        event = SimpleEvent.objects.filter(name="Final Match").first()
        assert event is not None
        assert event.event_type == Event.EventType.SIMPLE

    def test_creates_channel_from_event(self, db, mock_match_event):
        """Should create channel when processing event."""
        with (
            patch("soccertime.management.commands.scraping.example.ExampleSource.get_events") as mock_get,
            patch("soccertime.management.commands.scrapit.requests.get") as mock_requests,
        ):
            mock_get.return_value = iter([mock_match_event])
            mock_requests.return_value.status_code = 404
            call_command("scrapit", "--source=example", "--include-disabled")

        assert Channel.objects.filter(name="Test Channel").exists()

    def test_associates_channels_with_event(self, db, mock_match_event):
        """Should associate channels with created event."""
        with (
            patch("soccertime.management.commands.scraping.example.ExampleSource.get_events") as mock_get,
            patch("soccertime.management.commands.scrapit.requests.get") as mock_requests,
        ):
            mock_get.return_value = iter([mock_match_event])
            mock_requests.return_value.status_code = 404
            call_command("scrapit", "--source=example", "--include-disabled")

        match = Match.objects.filter(local__name="Test Home Team").first()
        assert match.channels.filter(name="Test Channel").exists()


class TestScrapingSourceBase:
    """Tests for scraping base module."""

    def test_get_available_sources(self):
        """Should return registered sources."""
        sources = get_available_sources()
        assert "futbolenlatv" in sources

    def test_list_source_names(self):
        """Should list source names."""
        names = list_source_names()
        assert "futbolenlatv" in names

    def test_source_has_required_properties(self):
        """Each source should have required properties."""
        sources = get_available_sources(include_disabled=True)
        for _name, source_class in sources.items():
            source = source_class()
            assert hasattr(source, "name")
            assert hasattr(source, "description")
            assert hasattr(source, "enabled")
            assert hasattr(source, "get_events")


class TestFutbolEnLaTVSource:
    """Integration tests for FutbolEnLaTV source."""

    @pytest.mark.integration
    def test_get_events_returns_iterator(self, db):
        """get_events should return an iterator."""
        from soccertime.management.commands.scraping.futbolenlatv import FutbolEnLaTVSource

        source = FutbolEnLaTVSource()
        events = source.get_events()
        assert hasattr(events, "__iter__")

    @pytest.mark.integration
    def test_get_events_yields_valid_events(self, db):
        """Events should have required fields."""
        from soccertime.management.commands.scraping.futbolenlatv import FutbolEnLaTVSource

        source = FutbolEnLaTVSource()

        # Get first event only
        for event in source.get_events():
            assert event.datetime is not None
            assert event.sport is not None
            assert event.competition is not None
            assert event.details is not None
            assert isinstance(event.channels, list)
            break  # Only test first event

    def test_source_properties(self):
        """Source should have correct properties."""
        from soccertime.management.commands.scraping.futbolenlatv import FutbolEnLaTVSource

        source = FutbolEnLaTVSource()
        assert source.name == "futbolenlatv"
        assert source.description is not None
        assert source.enabled is True


class TestScrapingHelpers:
    """Tests for scraping helper functions."""

    def test_clean_text(self):
        """clean_text should normalize whitespace."""
        from soccertime.management.commands.scraping.futbolenlatv import clean_text

        assert clean_text("  hello   world  ") == "hello world"
        assert clean_text(None) is None
        assert clean_text("") == ""

    def test_is_valid_date(self):
        """is_valid_date should validate date ranges."""
        from soccertime.management.commands.scraping.futbolenlatv import is_valid_date

        today = datetime.date.today()

        # Valid dates
        assert is_valid_date(today) is True
        assert is_valid_date(today + datetime.timedelta(days=30)) is True
        assert is_valid_date(today - datetime.timedelta(days=3)) is True

        # Invalid dates
        assert is_valid_date(today + datetime.timedelta(days=400)) is False
        assert is_valid_date(today - datetime.timedelta(days=30)) is False
        assert is_valid_date(None) is False
