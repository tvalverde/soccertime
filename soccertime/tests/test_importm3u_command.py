from io import StringIO
from unittest.mock import patch

import pytest
import requests
from django.core.management import call_command
from django.core.management.base import CommandError

from soccertime.models import Channel, ChannelLink, ChannelLinkSource

from .conftest import remote_text_response

M3U_HEADER = """#EXTM3U url-tvg="https://example.com/guide.xml" refresh="3600"
#EXTVLCOPT:network-caching=1000


"""


def write_m3u(tmp_path, content, filename="mundial.m3u"):
    playlist = tmp_path / filename
    playlist.write_text(M3U_HEADER + content, encoding="utf-8")
    return playlist


@pytest.mark.django_db
class TestImportM3uCommand:
    def test_importm3u_basic(self, tmp_path):
        channel = Channel.objects.create(name="DAZN Mundial 1")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 tvg-id="DAZN Mundial 1" tvg-logo="https://example.com/logo.webp" group-title="MUNDIAL",DAZN Mundial 1
acestream://1111111111111111111111111111111111111111
""",
        )

        call_command("importm3u", f"--file={playlist}")

        assert ChannelLink.objects.count() == 1
        link = ChannelLink.objects.first()
        assert link.name == "Dazn Mundial 1"
        assert link.subcategory == "Mundial"
        assert link.link == "acestream://1111111111111111111111111111111111111111"

        assert channel.links.filter(pk=link.pk).exists()

        source = ChannelLinkSource.objects.get(name="MUNDIAL")
        assert link.sources.filter(pk=source.pk).exists()

    def test_importm3u_same_link_from_two_sources_reuses_one_row(self, tmp_path):
        """The same URL imported twice must upsert a single row with both sources."""
        channel = Channel.objects.create(name="DAZN Mundial 1")
        entry = """#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
acestream://1111111111111111111111111111111111111111
"""

        call_command("importm3u", f"--file={write_m3u(tmp_path, entry)}", "--source=first")
        call_command("importm3u", f"--file={write_m3u(tmp_path, entry)}", "--source=second")

        assert ChannelLink.objects.count() == 1
        link = ChannelLink.objects.get()
        assert set(link.sources.values_list("name", flat=True)) == {"FIRST", "SECOND"}
        assert channel.links.filter(pk=link.pk).count() == 1

    def test_importm3u_source_override(self, tmp_path):
        Channel.objects.create(name="DAZN Mundial 1")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
acestream://1111111111111111111111111111111111111111
""",
        )

        call_command("importm3u", f"--file={playlist}", "--source=worldcup")

        assert ChannelLinkSource.objects.filter(name="WORLDCUP").exists()
        assert not ChannelLinkSource.objects.filter(name="MUNDIAL").exists()

    def test_importm3u_mirror_suffix_stripped(self, tmp_path):
        channel = Channel.objects.create(name="DAZN Mundial 1")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1 [2]
acestream://2222222222222222222222222222222222222222
""",
        )

        call_command("importm3u", f"--file={playlist}")

        link = ChannelLink.objects.get(link="acestream://2222222222222222222222222222222222222222")
        assert link.name == "Dazn Mundial 1"
        assert "[2]" not in link.name
        assert channel.links.filter(pk=link.pk).exists()

    def test_importm3u_quality_extraction(self, tmp_path):
        Channel.objects.create(name="CANAL 5 MX")
        Channel.objects.create(name="FOX ONE")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",CANAL 5 MX 1080p
acestream://3333333333333333333333333333333333333333

#EXTINF:-1 group-title="MUNDIAL",FOX ONE 4K
acestream://4444444444444444444444444444444444444444
""",
        )

        call_command("importm3u", f"--file={playlist}")

        fhd_link = ChannelLink.objects.get(link="acestream://3333333333333333333333333333333333333333")
        uhd_link = ChannelLink.objects.get(link="acestream://4444444444444444444444444444444444444444")
        assert fhd_link.quality == ChannelLink.Quality.FHD
        assert uhd_link.quality == ChannelLink.Quality.UHD

    def test_importm3u_unmatched_channel_stored_without_association(self, tmp_path):
        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",FUSSBALL TV
acestream://5555555555555555555555555555555555555555
""",
        )

        out = StringIO()
        call_command("importm3u", f"--file={playlist}", stdout=out)

        link = ChannelLink.objects.get(link="acestream://5555555555555555555555555555555555555555")
        assert link.channels.count() == 0
        assert link.sources.filter(name="MUNDIAL").exists()
        assert "Channel not found" in out.getvalue()

    def test_importm3u_dry_run(self, tmp_path):
        Channel.objects.create(name="DAZN Mundial 1")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
acestream://6666666666666666666666666666666666666666
""",
        )

        out = StringIO()
        call_command("importm3u", f"--file={playlist}", "--dry", stdout=out)

        assert ChannelLink.objects.count() == 0
        assert "DRY RUN" in out.getvalue()

    def test_importm3u_invalid_hash_skipped(self, tmp_path):
        """The broken entries are skipped with a warning while the valid one lands."""
        Channel.objects.create(name="DAZN Mundial 1")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
acestream://xyz

#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
123456789012345678901234567890123456789

#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
acestream://1111111111111111111111111111111111111111
""",
        )

        out = StringIO()
        call_command("importm3u", f"--file={playlist}", stdout=out)

        assert ChannelLink.objects.count() == 1
        assert "Invalid hash" in out.getvalue()
        assert "Non-acestream URL" in out.getvalue()

    def test_importm3u_non_acestream_url_skipped(self, tmp_path):
        Channel.objects.create(name="DAZN Mundial 1")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
http://example.com/stream.m3u8

#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
acestream://2222222222222222222222222222222222222222
""",
        )

        out = StringIO()
        call_command("importm3u", f"--file={playlist}", stdout=out)

        assert not ChannelLink.objects.filter(link="http://example.com/stream.m3u8").exists()
        assert ChannelLink.objects.count() == 1
        assert "Non-acestream URL" in out.getvalue()

    def test_importm3u_bare_hash_accepted(self, tmp_path):
        Channel.objects.create(name="DAZN Mundial 1")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
7777777777777777777777777777777777777777
""",
        )

        call_command("importm3u", f"--file={playlist}")

        assert ChannelLink.objects.filter(link="acestream://7777777777777777777777777777777777777777").exists()

    def test_importm3u_updates_existing_link(self, tmp_path):
        Channel.objects.create(name="DAZN Mundial 1")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
acestream://8888888888888888888888888888888888888888
""",
        )

        call_command("importm3u", f"--file={playlist}")
        out = StringIO()
        call_command("importm3u", f"--file={playlist}", stdout=out)

        assert ChannelLink.objects.count() == 1
        assert "Updated" in out.getvalue()

    def test_importm3u_generic_token_does_not_match_unrelated_channels(self, tmp_path):
        """Regression: "CANAL 5 MX" must not fuzzy-match every "Canal *" channel.

        The token fallback used to drop short tokens ("5", "mx") and match on the
        generic "canal" token alone, associating the link to unrelated channels.
        """
        Channel.objects.create(name="Canal Sur")
        Channel.objects.create(name="Canal Extremadura")
        Channel.objects.create(name="CANAL 9 SORIA YouTube")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",CANAL 5 MX 1080p
acestream://abcdefabcdefabcdefabcdefabcdefabcdefabcd
""",
        )

        out = StringIO()
        call_command("importm3u", f"--file={playlist}", stdout=out)

        link = ChannelLink.objects.get(link="acestream://abcdefabcdefabcdefabcdefabcdefabcdefabcd")
        assert link.channels.count() == 0
        assert "Channel not found" in out.getvalue()

    def test_importm3u_orphan_directives(self, tmp_path):
        Channel.objects.create(name="DAZN Mundial 1")

        playlist = write_m3u(
            tmp_path,
            """#EXTINF:-1 group-title="MUNDIAL",Orphan Without URL
#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1
acestream://9999999999999999999999999999999999999999

#EXTINF:-1 group-title="MUNDIAL",Trailing Orphan
""",
        )

        out = StringIO()
        call_command("importm3u", f"--file={playlist}", stdout=out)

        assert ChannelLink.objects.count() == 1
        output = out.getvalue()
        assert "EXTINF with no URL (skipped): Orphan Without URL" in output
        assert "EXTINF with no URL (skipped): Trailing Orphan" in output


@pytest.mark.django_db
class TestImportM3uFromUrl:
    """The playlist may live on a server, which is where these lists are published."""

    PLAYLIST = (
        '#EXTM3U\n#EXTINF:-1 group-title="MUNDIAL",DAZN Mundial 1\n'
        "acestream://1111111111111111111111111111111111111111\n"
    )
    URL = "https://example.com/lists/hashes_acestream.m3u"

    def fetching(self, body=PLAYLIST, **kwargs):
        return patch(
            "soccertime.management.commands._link_import_base.requests.get",
            return_value=remote_text_response(body.encode("utf-8"), **kwargs),
        )

    def test_importm3u_from_url(self):
        channel = Channel.objects.create(name="DAZN Mundial 1")

        with self.fetching():
            call_command("importm3u", f"--url={self.URL}")

        link = ChannelLink.objects.get(link="acestream://1111111111111111111111111111111111111111")
        assert channel.links.filter(pk=link.pk).exists()

    def test_importm3u_names_the_source_after_the_url_file(self):
        Channel.objects.create(name="DAZN Mundial 1")

        with self.fetching():
            call_command("importm3u", f"--url={self.URL}")

        assert ChannelLinkSource.objects.filter(name="HASHES_ACESTREAM").exists()

    def test_importm3u_source_override_wins_over_the_url(self):
        Channel.objects.create(name="DAZN Mundial 1")

        with self.fetching():
            call_command("importm3u", f"--url={self.URL}", "--source=tokyo")

        assert ChannelLinkSource.objects.filter(name="TOKYO").exists()
        assert not ChannelLinkSource.objects.filter(name="HASHES_ACESTREAM").exists()

    def test_importm3u_url_without_a_file_name_demands_a_source(self):
        with pytest.raises(CommandError, match="--source"):
            call_command("importm3u", "--url=https://example.com/")

    def test_importm3u_requires_an_origin(self):
        with pytest.raises(CommandError):
            call_command("importm3u")

    def test_importm3u_rejects_both_origins(self, tmp_path):
        with pytest.raises(CommandError):
            call_command("importm3u", f"--file={write_m3u(tmp_path, '')}", f"--url={self.URL}")

    def test_importm3u_reports_an_unreachable_url(self):
        with patch(
            "soccertime.management.commands._link_import_base.requests.get",
            side_effect=requests.Timeout("too slow"),
        ):
            with pytest.raises(CommandError, match="Could not fetch"):
                call_command("importm3u", f"--url={self.URL}")
