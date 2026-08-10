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
from django.db import IntegrityError, transaction

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

    def test_futbolenlatv_slug_nullable(self, db):
        """futbolenlatv_slug can be null."""
        team = Team.objects.create(name="No Slug Team", futbolenlatv_slug=None)
        assert team.futbolenlatv_slug is None

    def test_futbolenlatv_slug_unique(self, db):
        """futbolenlatv_slug must be unique."""
        Team.objects.create(name="Team 1", futbolenlatv_slug="slug")
        with pytest.raises(IntegrityError):
            Team.objects.create(name="Team 2", futbolenlatv_slug="slug")

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
        assert len(enabled) == 1
        assert enabled[0].enabled is True


class TestChannelLink:
    """Tests for ChannelLink model."""

    def test_str(self, channel_link):
        assert str(channel_link) == "Movistar LaLiga HD [HD]"

    def test_scheme(self, channel_link):
        assert channel_link.scheme == "https"

    def test_link_is_unique(self, db, channel_link):
        """Two rows may not share a URL: import_entries upserts on `link`."""
        with pytest.raises(IntegrityError), transaction.atomic():
            ChannelLink.objects.create(name="Duplicate", link=channel_link.link)

    def test_several_links_may_have_no_url(self, db):
        """The unique constraint must not collapse the rows still missing a URL."""
        ChannelLink.objects.create(name="Pending A")
        ChannelLink.objects.create(name="Pending B")

        assert ChannelLink.objects.filter(link__isnull=True).count() == 2

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


class TestChannelLinkOrphanCleanup:
    """Tests for the signals that remove links left without any source."""

    @pytest.fixture
    def manual_link(self, db):
        """A link created by hand (in the admin), which never gets a source."""
        return ChannelLink.objects.create(name="Manual", link="https://example.com/manual")

    def test_deleting_source_keeps_manual_links(self, channel_link_source, manual_link):
        """Links that never had a source belong to nobody and must survive."""
        channel_link_source.delete()
        assert ChannelLink.objects.filter(pk=manual_link.pk).exists()

    def test_deleting_source_deletes_its_orphan_links(self, channel_link, channel_link_source):
        channel_link_source.delete()
        assert not ChannelLink.objects.filter(pk=channel_link.pk).exists()

    def test_deleting_source_keeps_links_with_another_source(self, channel_link, channel_link_source):
        other_source = ChannelLinkSource.objects.create(name="other")
        channel_link.sources.add(other_source)

        channel_link_source.delete()

        assert ChannelLink.objects.filter(pk=channel_link.pk).exists()

    def test_removing_last_source_deletes_link(self, channel_link, channel_link_source):
        channel_link.sources.remove(channel_link_source)
        assert not ChannelLink.objects.filter(pk=channel_link.pk).exists()

    def test_clearing_sources_deletes_link(self, channel_link):
        channel_link.sources.clear()
        assert not ChannelLink.objects.filter(pk=channel_link.pk).exists()

    def test_removing_link_from_source_side_deletes_orphan(self, channel_link, channel_link_source):
        """The reverse direction is what the admin form uses."""
        channel_link_source.links.remove(channel_link)
        assert not ChannelLink.objects.filter(pk=channel_link.pk).exists()

    def test_clearing_links_from_source_side_deletes_orphans(self, channel_link, channel_link_source):
        channel_link_source.links.clear()
        assert not ChannelLink.objects.filter(pk=channel_link.pk).exists()

    def test_removing_link_from_source_side_keeps_link_with_another_source(self, channel_link, channel_link_source):
        other_source = ChannelLinkSource.objects.create(name="other")
        channel_link.sources.add(other_source)

        channel_link_source.links.remove(channel_link)

        assert ChannelLink.objects.filter(pk=channel_link.pk).exists()

    def test_removing_link_from_source_side_keeps_manual_links(self, channel_link, channel_link_source, manual_link):
        channel_link_source.links.remove(channel_link)
        assert ChannelLink.objects.filter(pk=manual_link.pk).exists()


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


class TestCodeReviewRegressions:
    """Regression tests for Code Review Points 1 and 4."""

    def test_manager_no_implicit_with_related(self):
        """
        Point 1: EventManager should not implicitly call with_related()
        on get_queryset(), avoiding unnecessary JOINs for count() etc.
        """
        qs = Event.objects.all()
        assert qs.query.select_related is False
        assert not qs._prefetch_related_lookups

    def test_manager_explicit_with_related(self):
        """
        Point 1: EventManager should provide with_related() explicitly.
        """
        qs = Event.objects.with_related()
        assert qs.query.select_related is not False
        assert qs._prefetch_related_lookups

    def test_competition_properties_use_prefetch(self, db, django_assert_max_num_queries, competition, match):
        """
        Point 4: Competition properties should not do N+1 queries.
        They should use list comprehensions to leverage prefetch cache.
        """
        comp = Competition.objects.prefetch_related("events", "favorite").get(id=competition.id)

        # Access properties and ensure they don't hit the DB
        with django_assert_max_num_queries(0):
            _ = comp.is_favorite
            _ = comp.has_events
            _ = comp.events_count


class TestEventDuration:
    """Tests for Event duration and date_end property."""

    def test_default_duration(self, match):
        import datetime

        assert match.duration is None
        assert match.date_end == match.date + datetime.timedelta(hours=2)

    def test_custom_duration(self, match):
        import datetime

        match.duration = datetime.timedelta(minutes=90)
        match.save()
        match.refresh_from_db()
        assert match.date_end == match.date + datetime.timedelta(minutes=90)

    def test_duration_across_midnight(self, db, competition):
        import datetime

        from django.utils import timezone

        start_time = timezone.now().replace(hour=23, minute=0, second=0, microsecond=0)
        event = Event.objects.create(
            competition=competition,
            date=start_time,
            duration=datetime.timedelta(hours=3),
        )
        assert event.date_end.day != start_time.day
        assert event.date_end == start_time + datetime.timedelta(hours=3)


class TestChannelLinkURLValidation:
    """Tests for ChannelLink.link URL validation with custom schemes."""

    @pytest.mark.parametrize(
        "valid_url",
        [
            "https://stream.example.com/live",
            "http://192.168.1.1:8080/channel",
            "acestream://1234567890abcdef1234567890abcdef12345678",
            "sop://broker.sopcast.com:3912/123456",
            "intent://stream#Intent;scheme=acestream;end",
            "rtmp://rtmp.example.com/live/stream",
            "http://example.com/playlist.m3u8",
        ],
    )
    def test_valid_link_schemes(self, db, valid_url):
        link_obj = ChannelLink(name="Test Stream", link=valid_url)
        link_obj.full_clean()  # Should not raise ValidationError

    def test_invalid_link_url(self, db):
        link_obj = ChannelLink(name="Bad Stream", link="not-a-valid-url")
        with pytest.raises(ValidationError):
            link_obj.full_clean()


class TestFavoriteStrCornerCases:
    """Tests for Favorite.__str__ corner cases."""

    def test_favorite_team_and_competition(self, favorite_team, team_home, competition):
        assert str(favorite_team) == f"{team_home} @ {competition}"

    def test_favorite_team_only(self, db, team_home):
        fav = Favorite.objects.create(team=team_home)
        assert str(fav) == str(team_home)

    def test_favorite_competition_only(self, favorite_competition, competition):
        assert str(favorite_competition) == competition.name

    def test_favorite_neither(self):
        fav = Favorite()
        assert str(fav) == "Favorite"


class TestAsManagerForwarding:
    """Tests to verify EventQuerySet methods work via Event.objects manager."""

    def test_manager_methods_forwarded(self, match, race, simple_event):
        match_pks = set(Event.objects.matches().values_list("pk", flat=True))
        race_pks = set(Event.objects.races().values_list("pk", flat=True))
        simple_pks = set(Event.objects.simple_events().values_list("pk", flat=True))

        assert match.pk in match_pks
        assert race.pk in race_pks
        assert simple_event.pk in simple_pks
        assert Event.objects.today_onwards().exists()
        assert Event.objects.search("Madrid").exists()


class TestSoccertimeTemplateTags:
    """Tests for custom template tags/filters."""

    def test_render_image_markup_with_none(self):
        from soccertime.templatetags.soccertime_tags import render_image_markup

        result = render_image_markup(None)
        assert "<svg" in result

    def test_render_image_markup_with_obj(self, team_home):
        from soccertime.templatetags.soccertime_tags import render_image_markup

        result = render_image_markup(team_home)
        assert "<svg" in result
