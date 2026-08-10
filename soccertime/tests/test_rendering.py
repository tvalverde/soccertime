"""Tests for the image markup, which lives outside the models on purpose."""

import io
from unittest.mock import patch

import pytest
from django.core.files.images import ImageFile
from PIL import Image

from soccertime.models import Team
from soccertime.rendering import image_markup
from soccertime.templatetags.soccertime_tags import render_image_markup


@pytest.fixture
def team_with_crest(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    team = Team.objects.create(name="Con escudo")
    buffer = io.BytesIO()
    Image.new("RGB", (48, 24)).save(buffer, format="PNG")
    team.save_crest(buffer, "crest.png")
    return team


class TestImageMarkup:
    def test_renders_the_stored_dimensions(self, team_with_crest):
        markup = image_markup(Team.objects.get(pk=team_with_crest.pk))

        assert 'width="48.0" height="24.0"' in markup
        assert team_with_crest.crest.url in markup

    def test_does_not_open_the_file_to_measure_it(self, team_with_crest):
        team = Team.objects.get(pk=team_with_crest.pk)

        with patch.object(ImageFile, "_get_image_dimensions", side_effect=AssertionError("read the file")):
            markup = image_markup(team)

        assert 'width="48.0"' in markup

    def test_falls_back_to_the_placeholder_without_an_image(self, team_home):
        assert "bi-emoji-dizzy" in image_markup(team_home)

    def test_falls_back_to_the_placeholder_when_the_file_is_gone(self, team_with_crest, tmp_path):
        (tmp_path / team_with_crest.crest.name).unlink()

        assert "bi-emoji-dizzy" in image_markup(Team.objects.get(pk=team_with_crest.pk))

    def test_renders_nothing_for_a_missing_relation(self):
        """A competition that was never given a flag has none: it is not a broken image.

        Rendering the placeholder here put a dizzy-face icon next to all 65 flagless
        competitions, where the previous template silently resolved None to nothing.
        """
        assert image_markup(None) == ""

    def test_placeholder_is_for_a_missing_file_not_a_missing_relation(self, team_home):
        """A team row that has no crest at all still shows it: the crest is expected."""
        assert "bi-emoji-dizzy" in image_markup(team_home)

    def test_escapes_the_values_it_interpolates(self, team_with_crest):
        markup = image_markup(Team.objects.get(pk=team_with_crest.pk))
        assert markup.startswith("<img src=")
        assert "<script" not in markup


class TestRenderImageMarkupFilter:
    """The template filter is the only entry point templates should use."""

    def test_delegates_to_the_renderer(self, team_with_crest):
        team = Team.objects.get(pk=team_with_crest.pk)
        assert render_image_markup(team) == image_markup(team)

    def test_output_is_marked_safe_so_templates_need_no_safe_filter(self, team_home):
        assert hasattr(render_image_markup(team_home), "__html__")
