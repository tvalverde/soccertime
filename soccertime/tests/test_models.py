"""
Tests for soccertime models.

Tests cover:
- Model creation and string representation
- Validations (clean methods)
- Constraints (database-level)
- Properties and computed fields
- Auto-set fields (event_type)
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from soccertime.models import (
    ChannelLink,
    ChannelLinkSource,
    Competition,
    Event,
    Favorite,
    Sport,
    Team,
)


class TestSport:
    """Tests for Sport model."""

    def test_str(self, sport):
        assert str(sport) == "Fútbol"

    def test_ordering(self, sports):
        """Sports should be ordered by 'order' field."""
        ordered = Sport.objects.all()
        assert list(ordered) == sorted(sports, key=lambda s: s.order)

    def test_competitions_with_events(self, sport, competition, match):
        """Should return competitions that have upcoming events."""
        comps = sport.competitions_with_events
        assert competition in comps

    def test_competitions_without_events(self, sport, competition):
        """Should return competitions without upcoming events."""
        comps = sport.competitions_without_events
        assert competition in comps


class TestFlag:
    """Tests for Flag model."""

    def test_str(self, flag):
        assert str(flag) == "spain"

    def test_flag_image_without_image(self, flag):
        """Should return fallback SVG when no image."""
        result = flag.flag_image()
        assert "<svg" in result
        assert "bi-emoji-dizzy" in result


class TestCompetition:
    """Tests for Competition model."""

    def test_str(self, competition):
        assert str(competition) == "La Liga"

    def test_unique_together(self, db, sport, flag):
        """Competition name must be unique per sport."""
        Competition.objects.create(name="Test League", sport=sport, flag=flag)
        with pytest.raises(IntegrityError):
            Competition.objects.create(name="Test League", sport=sport, flag=flag)

    def test_is_favorite_false(self, competition):
        assert competition.is_favorite is False

    def test_is_favorite_true(self, competition, favorite_competition):
        assert competition.is_favorite is True

    def test_has_events_false(self, competition):
        assert competition.has_events is False

    def test_has_events_true(self, competition, match):
        assert competition.has_events is True

    def test_events_count(self, competition, match, match_in_progress):
        """Should count only upcoming events."""
        # match is in future, match_in_progress started 1 hour ago
        # Both should be counted as they're today
        assert competition.events_count >= 1


class TestTeam:
    """Tests for Team model."""

    def test_str(self, team_home):
        assert str(team_home) == "Real Madrid"

    def test_unique_name(self, db):
        """Team name must be unique."""
        Team.objects.create(name="Test Team")
        with pytest.raises(IntegrityError):
            Team.objects.create(name="Test Team")

    def test_crest_image_without_crest(self, team_home):
        """Should return fallback SVG when no crest."""
        result = team_home.crest_image()
        assert "<svg" in result


class TestChannel:
    """Tests for Channel model."""

    def test_str(self, channel):
        assert str(channel) == "Movistar LaLiga"

    def test_enabled_links(self, channel_with_links):
        """Should return only enabled links."""
        enabled = channel_with_links.enabled_links
        assert enabled.count() == 1
        assert enabled.first().enabled is True


class TestChannelLink:
    """Tests for ChannelLink model."""

    def test_str(self, channel_link):
        assert str(channel_link) == "Movistar LaLiga HD [HD]"

    def test_scheme(self, channel_link):
        assert channel_link.scheme == "https"

    def test_quality_choices(self, db):
        """All quality choices should be valid."""
        source, _ = ChannelLinkSource.objects.get_or_create(name="test")
        for quality in ChannelLink.Quality:
            link = ChannelLink.objects.create(
                name=f"Test {quality}",
                quality=quality,
                link=f"https://example.com/{quality}",
            )
            link.sources.add(source)
            assert link.quality == quality


class TestFavorite:
    """Tests for Favorite model."""

    def test_str_with_team(self, favorite_team):
        assert "Real Madrid" in str(favorite_team)
        assert "La Liga" in str(favorite_team)

    def test_str_without_team(self, favorite_competition):
        assert str(favorite_competition) == "La Liga"

    def test_clean_raises_when_both_null(self, db):
        """Should raise ValidationError when both competition and team are null."""
        favorite = Favorite(competition=None, team=None)
        with pytest.raises(ValidationError) as exc_info:
            favorite.clean()
        assert "At least one" in str(exc_info.value)

    def test_clean_passes_with_competition(self, db, competition):
        """Should pass validation with only competition."""
        favorite = Favorite(competition=competition, team=None)
        favorite.clean()  # Should not raise

    def test_clean_passes_with_team(self, db, team_home, competition):
        """Should pass validation with team (and competition)."""
        favorite = Favorite(competition=competition, team=team_home)
        favorite.clean()  # Should not raise

    def test_constraint_prevents_both_null(self, db):
        """Database constraint should prevent both fields being null."""
        with pytest.raises(IntegrityError):
            # Bypass clean() by using raw SQL or direct create
            Favorite.objects.create(competition=None, team=None, order=99)


class TestEvent:
    """Tests for Event base model."""

    def test_event_type_is_readonly(self, match):
        """event_type should not be directly editable."""
        # The field has editable=False, so it won't appear in forms
        assert match._meta.get_field("event_type").editable is False


class TestMatch:
    """Tests for Match model."""

    def test_str(self, match):
        assert str(match) == "Real Madrid - FC Barcelona"

    def test_event_type_auto_set(self, match):
        """event_type should be automatically set to 'match'."""
        assert match.event_type == Event.EventType.MATCH

    def test_event_type_persists_on_save(self, match):
        """event_type should remain 'match' after save."""
        match.details = "Updated"
        match.save()
        match.refresh_from_db()
        assert match.event_type == Event.EventType.MATCH

    def test_inherits_from_event(self, match):
        """Match should be accessible via Event.objects."""
        event = Event.objects.get(pk=match.pk)
        assert event.event_type == Event.EventType.MATCH


class TestRace:
    """Tests for Race model."""

    def test_str(self, race):
        assert str(race) == "Etapa 15 - Montaña"

    def test_event_type_auto_set(self, race):
        """event_type should be automatically set to 'race'."""
        assert race.event_type == Event.EventType.RACE


class TestSimpleEvent:
    """Tests for SimpleEvent model."""

    def test_str(self, simple_event):
        assert str(simple_event) == "Final Masculina"

    def test_event_type_auto_set(self, simple_event):
        """event_type should be automatically set to 'simple'."""
        assert simple_event.event_type == Event.EventType.SIMPLE


class TestImageMixin:
    """Tests for ImageMixin functionality."""

    def test_render_image_fallback(self, team_home):
        """Should render fallback SVG when image doesn't exist."""
        result = team_home.render_image()
        assert "<svg" in result
        assert "bi-emoji-dizzy" in result

    def test_flag_render_image_fallback(self, flag):
        """Flag should also use the mixin correctly."""
        result = flag.render_image()
        assert "<svg" in result
