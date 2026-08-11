"""Tests for the command that restores flag images missing from storage."""

import io
from io import StringIO
from unittest.mock import patch

import pytest
import requests
from django.core.management import call_command
from PIL import Image

from soccertime.models import Flag, Team

from .conftest import image_response


def image_bytes(size=(32, 24)):
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, format="PNG")
    return buffer


@pytest.fixture
def stored_flag(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    flag = Flag.objects.create(name="https://example.com/spain.png", display_name="España")
    flag.save_flag(image_bytes())
    return flag


@pytest.fixture
def flag_without_file(stored_flag, tmp_path):
    """A row pointing at media that is no longer on disk, as seen in production."""
    (tmp_path / stored_flag.image.name).unlink()
    return stored_flag


@pytest.mark.django_db
class TestRedownloadImagesCommand:
    def test_reports_nothing_missing_when_every_file_is_present(self, stored_flag):
        out = StringIO()
        call_command("redownload_images", stdout=out)
        assert "flags whose file is missing: 0" in out.getvalue()

    def test_reports_crests_that_cannot_be_restored(self, db, settings, tmp_path):
        """A team keeps no source URL, so its crest is reported but never re-fetched."""
        settings.MEDIA_ROOT = tmp_path
        broken = Team.objects.create(name="Sin fichero")
        broken.save_crest(image_bytes())
        (tmp_path / broken.crest.name).unlink()
        Team.objects.create(name="Sin escudo")

        out = StringIO()
        with patch("soccertime.management.commands._image_download.requests.get") as mock_get:
            call_command("redownload_images", stdout=out)

        mock_get.assert_not_called()
        assert "teams whose crest file is missing: 1" in out.getvalue()
        assert "teams with no crest at all:        1" in out.getvalue()

    def test_restores_a_missing_file_from_its_source_url(self, flag_without_file, public_dns):
        out = StringIO()
        with patch("soccertime.management.commands._image_download.requests.get") as mock_get:
            mock_get.return_value = image_response(image_bytes().getvalue())
            call_command("redownload_images", stdout=out)

        mock_get.assert_called_once()
        assert mock_get.call_args[0][0] == "https://example.com/spain.png"
        assert "Restored 1 of 1" in out.getvalue()

        flag_without_file.refresh_from_db()
        assert flag_without_file.image.storage.exists(flag_without_file.image.name)
        assert (flag_without_file.image_width, flag_without_file.image_height) == (32, 24)

    def test_dry_run_downloads_nothing(self, flag_without_file):
        out = StringIO()
        with patch("soccertime.management.commands._image_download.requests.get") as mock_get:
            call_command("redownload_images", "--dry-run", stdout=out)

        mock_get.assert_not_called()
        assert "Dry run" in out.getvalue()
        assert flag_without_file.name in out.getvalue()

    def test_a_failed_download_does_not_stop_the_others(self, db, settings, tmp_path, public_dns):
        settings.MEDIA_ROOT = tmp_path
        for index in range(2):
            flag = Flag.objects.create(name=f"https://example.com/{index}.png", display_name=str(index))
            flag.save_flag(image_bytes())
            (tmp_path / flag.image.name).unlink()

        out, err = StringIO(), StringIO()
        with patch("soccertime.management.commands._image_download.requests.get") as mock_get:
            mock_get.side_effect = [
                requests.ConnectionError("boom"),
                image_response(image_bytes().getvalue()),
            ]
            call_command("redownload_images", stdout=out, stderr=err)

        assert "Restored 1 of 2" in out.getvalue()
        assert "Still missing: 1" in out.getvalue()
