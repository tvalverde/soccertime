from unittest.mock import patch

import pytest
import requests
from django.core.management import call_command
from django.core.management.base import CommandError

from soccertime.models import Channel, ChannelLink, ChannelLinkSource

from .conftest import remote_text_response

TOKYO_URL = "https://git.gay/TokyoGhoulles/AceStream_IDs/raw/branch/main/hashes_acestream.m3u"

TOKYO_PLAYLIST = """#EXTM3U
#EXTINF:-1 tvg-id="DAZN 1" group-title="DEPORTES",DAZN 1 FHD
acestream://1111111111111111111111111111111111111111
"""


def fetching(body, **kwargs):
    """Patch the fetch the base command performs, answering with `body`."""
    return patch(
        "soccertime.management.commands._link_import_base.requests.get",
        return_value=remote_text_response(body.encode("utf-8") if isinstance(body, str) else body, **kwargs),
    )


@pytest.mark.django_db
class TestAddLinkSourceCommand:
    def test_addlinksource_newera_basic(self, tmp_path):
        """Test basic functionality with newera source format."""
        # 1. Setup Data
        channel = Channel.objects.create(name="DAZN 1")

        # 2. Create dummy source file
        source_file = tmp_path / "test_newera.txt"
        source_content = """DAZN 1 FHD --> NEW ERA
acestream://1234567890123456789012345678901234567890
"""
        source_file.write_text(source_content, encoding="utf-8")

        # 3. Run command
        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        # 4. Verify results
        assert ChannelLink.objects.count() == 1
        link = ChannelLink.objects.first()
        assert link.name == "Dazn 1"  # Normalized
        assert link.quality == ChannelLink.Quality.FHD
        assert link.link == "acestream://1234567890123456789012345678901234567890"

        # Verify association
        assert channel.links.filter(pk=link.pk).exists()

        # Verify Source created
        assert ChannelLinkSource.objects.filter(name="NEWERA").exists()

    def test_addlinksource_elcano_basic(self, tmp_path):
        """Test basic functionality with elcano source format."""
        # 1. Setup Data
        channel = Channel.objects.create(name="La 1 TVE")

        # 2. Create dummy source file
        source_file = tmp_path / "test_elcano.txt"
        source_content = """=== TDT ===

La 1
acestream://abcdefabcdefabcdefabcdefabcdefabcdefabcd
"""
        source_file.write_text(source_content, encoding="utf-8")

        # 3. Run command
        call_command("addlinksource", "--source=elcano", f"--file={source_file}")

        # 4. Verify results
        assert ChannelLink.objects.count() == 1
        link = ChannelLink.objects.first()
        # "La 1" should be normalized/cleaned
        assert "La 1" in link.name
        assert link.link == "acestream://abcdefabcdefabcdefabcdefabcdefabcdefabcd"

        # Verify association
        assert channel.links.filter(pk=link.pk).exists()

    def test_addlinksource_newera_dazn_variant_does_not_match_generic_dazn(self, tmp_path):
        dazn_generic = Channel.objects.create(name="DAZN (Ver en directo)")
        dazn_one = Channel.objects.create(name="DAZN 1")

        source_file = tmp_path / "test_newera_dazn_variant.txt"
        source_content = """DAZN 1 --> NEW ERA
acestream://2222222222222222222222222222222222222222
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://2222222222222222222222222222222222222222")
        assert dazn_one.links.filter(pk=link.pk).exists()
        assert not dazn_generic.links.filter(pk=link.pk).exists()

    def test_addlinksource_elcano_dazn_f1_does_not_match_generic_dazn(self, tmp_path):
        dazn_generic = Channel.objects.create(name="DAZN (Ver en directo)")
        dazn_f1 = Channel.objects.create(name="DAZN F1")

        source_file = tmp_path / "test_elcano_dazn_f1.txt"
        source_content = """=== DEPORTES ===

DAZN F1
acestream://3333333333333333333333333333333333333333
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=elcano", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://3333333333333333333333333333333333333333")
        assert dazn_f1.links.filter(pk=link.pk).exists()
        assert not dazn_generic.links.filter(pk=link.pk).exists()

    def test_addlinksource_newera_acb_evento_maps_to_dazn_baloncesto(self, tmp_path):
        baloncesto_1 = Channel.objects.create(name="DAZN Baloncesto 1")

        source_file = tmp_path / "test_newera_acb_evento.txt"
        source_content = """ACB EVENTO 01 --> NEW ERA
acestream://5555555555555555555555555555555555555555
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://5555555555555555555555555555555555555555")
        assert baloncesto_1.links.filter(pk=link.pk).exists()

    def test_addlinksource_elcano_dazn_acb_maps_to_dazn_baloncesto(self, tmp_path):
        baloncesto_2 = Channel.objects.create(name="DAZN Baloncesto 2")

        source_file = tmp_path / "test_elcano_dazn_acb.txt"
        source_content = """=== BALONCESTO ===

DAZN ACB 2
acestream://6666666666666666666666666666666666666666
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=elcano", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://6666666666666666666666666666666666666666")
        assert baloncesto_2.links.filter(pk=link.pk).exists()

    def test_addlinksource_newera_eleven_dazn_maps_to_dazn(self, tmp_path):
        """'ELEVEN DAZN N' is the Portuguese/Belgian operator alias for DAZN N."""
        dazn_1 = Channel.objects.create(name="DAZN 1")
        dazn_2 = Channel.objects.create(name="DAZN 2")

        source_file = tmp_path / "test_newera_eleven_dazn.txt"
        source_content = """ELEVEN DAZN 1 HD --> SPORT TV
acestream://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
ELEVEN DAZN 2 --> SPORT TV
acestream://bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link1 = ChannelLink.objects.get(link="acestream://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        link2 = ChannelLink.objects.get(link="acestream://bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        assert dazn_1.links.filter(pk=link1.pk).exists()
        assert dazn_2.links.filter(pk=link2.pk).exists()

    def test_addlinksource_newera_nba_eventos_maps_to_nba_league_pass(self, tmp_path):
        nba = Channel.objects.create(name="NBA League Pass")

        source_file = tmp_path / "test_newera_nba_eventos.txt"
        source_content = """NBA EVENTOS 1 --> NEW ERA
acestream://cccccccccccccccccccccccccccccccccccccccc
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://cccccccccccccccccccccccccccccccccccccccc")
        assert nba.links.filter(pk=link.pk).exists()

    def test_addlinksource_newera_dazn_eventos_maps_to_dazn(self, tmp_path):
        dazn_2 = Channel.objects.create(name="DAZN 2")

        source_file = tmp_path / "test_newera_dazn_eventos.txt"
        source_content = """DAZN EVENTOS 2 --> NEW ERA
acestream://dddddddddddddddddddddddddddddddddddddddd
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://dddddddddddddddddddddddddddddddddddddddd")
        assert dazn_2.links.filter(pk=link.pk).exists()

    def test_addlinksource_newera_1rfef_maps_to_rfef_tv(self, tmp_path):
        rfef = Channel.objects.create(name="RFEF TV YouTube")

        source_file = tmp_path / "test_newera_1rfef.txt"
        source_content = """Canal 1 (1RFEF) (SOLO EVENTOS) --> NEW ERA V
acestream://eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
        assert rfef.links.filter(pk=link.pk).exists()

    def test_addlinksource_newera_canal_de_tenis_maps_to_tennis_channel(self, tmp_path):
        tennis = Channel.objects.create(name="Tennis Channel")

        source_file = tmp_path / "test_newera_canal_tenis.txt"
        source_content = """Canal de Tenis HD (ES) --> SPORT TV
acestream://ffffffffffffffffffffffffffffffffffffffff
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://ffffffffffffffffffffffffffffffffffffffff")
        assert tennis.links.filter(pk=link.pk).exists()

    def test_addlinksource_newera_accepts_a_spaceless_separator(self, tmp_path):
        """Real lists glue the name to the arrow ("DAZN FIFA 1--> NEW ERA III").

        Each of those lines names its own numbered channel, so the pair must keep the
        number with the name and land on that channel alone.
        """
        fifa_1 = Channel.objects.create(name="DAZN FIFA 1")
        fifa_2 = Channel.objects.create(name="DAZN FIFA 2")

        source_file = tmp_path / "test_newera_spaceless_separator.txt"
        source_file.write_text(
            "DAZN FIFA 1--> NEW ERA III\nacestream://7777777777777777777777777777777777777777\n"
            "DAZN FIFA 2--> NEW ERA III\nacestream://8888888888888888888888888888888888888888\n",
            encoding="utf-8",
        )

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link_1 = ChannelLink.objects.get(link="acestream://7777777777777777777777777777777777777777")
        link_2 = ChannelLink.objects.get(link="acestream://8888888888888888888888888888888888888888")
        assert fifa_1.links.filter(pk=link_1.pk).exists()
        assert fifa_2.links.filter(pk=link_2.pk).exists()
        assert not fifa_1.links.filter(pk=link_2.pk).exists()
        assert not fifa_2.links.filter(pk=link_1.pk).exists()

    def test_addlinksource_update_keeps_quality_when_the_entry_carries_none(self, tmp_path):
        """A later list naming the same hash untagged must not erase a known quality."""
        Channel.objects.create(name="DAZN 1")
        link_url = "acestream://1212121212121212121212121212121212121212"

        tagged_file = tmp_path / "tagged.txt"
        tagged_file.write_text(f"DAZN 1 FHD --> NEW ERA\n{link_url}\n", encoding="utf-8")
        call_command("addlinksource", "--source=newera", f"--file={tagged_file}")

        untagged_file = tmp_path / "untagged.txt"
        untagged_file.write_text(f"DAZN 1 --> ELCANO\n{link_url}\n", encoding="utf-8")
        call_command("addlinksource", "--source=newera", f"--file={untagged_file}")

        link = ChannelLink.objects.get(link=link_url)
        assert link.quality == ChannelLink.Quality.FHD

    def test_addlinksource_update_retags_quality_when_the_entry_names_one(self, tmp_path):
        """An explicit tag is information, and a different one replaces the stored quality."""
        Channel.objects.create(name="DAZN 1")
        link_url = "acestream://3434343434343434343434343434343434343434"

        fhd_file = tmp_path / "fhd.txt"
        fhd_file.write_text(f"DAZN 1 FHD --> NEW ERA\n{link_url}\n", encoding="utf-8")
        call_command("addlinksource", "--source=newera", f"--file={fhd_file}")

        hd_file = tmp_path / "hd.txt"
        hd_file.write_text(f"DAZN 1 HD --> ELCANO\n{link_url}\n", encoding="utf-8")
        call_command("addlinksource", "--source=newera", f"--file={hd_file}")

        link = ChannelLink.objects.get(link=link_url)
        assert link.quality == ChannelLink.Quality.HD

    def test_addlinksource_newera_sky_sports_laliga_maps_to_dazn_laliga(self, tmp_path):
        dazn_laliga = Channel.objects.create(name="DAZN LaLiga")

        source_file = tmp_path / "test_newera_sky_laliga.txt"
        source_content = """Sky Sports LaLiga HD --> NEW ERA
acestream://9999999999999999999999999999999999999999
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://9999999999999999999999999999999999999999")
        assert dazn_laliga.links.filter(pk=link.pk).exists()


@pytest.mark.django_db
class TestAddLinkSourceUnmatchedAndPrune:
    """Unmatched links are stored, and every import prunes its source to its list."""

    def test_unmatched_entry_is_stored_without_channel(self, tmp_path, capsys):
        source_file = tmp_path / "newera.txt"
        source_file.write_text(
            "Totally Unknown Channel --> NEW ERA\nacestream://1111111111111111111111111111111111111111\n",
            encoding="utf-8",
        )

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://1111111111111111111111111111111111111111")
        assert link.channels.count() == 0
        assert link.sources.filter(name="NEWERA").exists()
        output = capsys.readouterr().out
        assert "Unmatched links (stored)" in output

    def test_prune_removes_delisted_link_and_deletes_orphan(self, tmp_path, capsys):
        Channel.objects.create(name="DAZN 1")
        Channel.objects.create(name="DAZN 2")

        both = tmp_path / "both.txt"
        both.write_text(
            "DAZN 1 --> NEW ERA\nacestream://1111111111111111111111111111111111111111\n"
            "DAZN 2 --> NEW ERA\nacestream://2222222222222222222222222222222222222222\n",
            encoding="utf-8",
        )
        call_command("addlinksource", "--source=newera", f"--file={both}")

        only_first = tmp_path / "only_first.txt"
        only_first.write_text(
            "DAZN 1 --> NEW ERA\nacestream://1111111111111111111111111111111111111111\n",
            encoding="utf-8",
        )
        call_command("addlinksource", "--source=newera", f"--file={only_first}")

        assert ChannelLink.objects.filter(link="acestream://1111111111111111111111111111111111111111").exists()
        assert not ChannelLink.objects.filter(link="acestream://2222222222222222222222222222222222222222").exists()
        assert "Pruned from source" in capsys.readouterr().out

    def test_prune_spares_link_alive_in_another_source(self, tmp_path):
        Channel.objects.create(name="DAZN 1")
        shared = "DAZN 1\nacestream://3333333333333333333333333333333333333333\n"

        elcano_file = tmp_path / "elcano.txt"
        elcano_file.write_text(f"=== DAZN ===\n\n{shared}", encoding="utf-8")
        call_command("addlinksource", "--source=elcano", f"--file={elcano_file}")

        newera_file = tmp_path / "newera.txt"
        newera_file.write_text(
            "DAZN 1 --> NEW ERA\nacestream://3333333333333333333333333333333333333333\n",
            encoding="utf-8",
        )
        call_command("addlinksource", "--source=newera", f"--file={newera_file}")

        elcano_without = tmp_path / "elcano_without.txt"
        elcano_without.write_text(
            "=== DAZN ===\n\nDAZN 1\nacestream://4444444444444444444444444444444444444444\n",
            encoding="utf-8",
        )
        call_command("addlinksource", "--source=elcano", f"--file={elcano_without}")

        survivor = ChannelLink.objects.get(link="acestream://3333333333333333333333333333333333333333")
        assert [source.name for source in survivor.sources.all()] == ["NEWERA"]

    def test_prune_ignores_handmade_sourceless_links(self, tmp_path):
        Channel.objects.create(name="DAZN 1")
        handmade = ChannelLink.objects.create(
            name="Handmade", link="acestream://5555555555555555555555555555555555555555"
        )

        source_file = tmp_path / "newera.txt"
        source_file.write_text(
            "DAZN 1 --> NEW ERA\nacestream://6666666666666666666666666666666666666666\n",
            encoding="utf-8",
        )
        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        assert ChannelLink.objects.filter(pk=handmade.pk).exists()

    def test_zero_valid_entries_aborts_without_pruning(self, tmp_path):
        """An empty parse reads as a truncated download, and pruning on it would wipe the source."""
        Channel.objects.create(name="DAZN 1")
        seeded = tmp_path / "seeded.txt"
        seeded.write_text(
            "DAZN 1 --> NEW ERA\nacestream://7777777777777777777777777777777777777777\n",
            encoding="utf-8",
        )
        call_command("addlinksource", "--source=newera", f"--file={seeded}")

        garbage = tmp_path / "garbage.txt"
        garbage.write_text("no arrow here\nnothing valid either\n", encoding="utf-8")
        with pytest.raises(CommandError, match="No valid entries"):
            call_command("addlinksource", "--source=newera", f"--file={garbage}")

        link = ChannelLink.objects.get(link="acestream://7777777777777777777777777777777777777777")
        assert link.sources.filter(name="NEWERA").exists()

    def test_dry_run_reports_prune_but_changes_nothing(self, tmp_path, capsys):
        Channel.objects.create(name="DAZN 1")
        Channel.objects.create(name="DAZN 2")
        both = tmp_path / "both.txt"
        both.write_text(
            "DAZN 1 --> NEW ERA\nacestream://8888888888888888888888888888888888888888\n"
            "DAZN 2 --> NEW ERA\nacestream://9999999999999999999999999999999999999999\n",
            encoding="utf-8",
        )
        call_command("addlinksource", "--source=newera", f"--file={both}")
        capsys.readouterr()

        only_first = tmp_path / "only_first.txt"
        only_first.write_text(
            "DAZN 1 --> NEW ERA\nacestream://8888888888888888888888888888888888888888\n",
            encoding="utf-8",
        )
        call_command("addlinksource", "--source=newera", f"--file={only_first}", "--dry")

        assert "Pruned from source" in capsys.readouterr().out
        delisted = ChannelLink.objects.get(link="acestream://9999999999999999999999999999999999999999")
        assert delisted.sources.filter(name="NEWERA").exists()

    def test_rejected_scheme_entry_is_not_counted_as_seen(self):
        """A row the project refuses to store must not stay attached through a rejected entry."""
        from soccertime.management.commands.addlinksource import Command
        from soccertime.models import ChannelLinkSource

        source, _ = ChannelLinkSource.get_or_create_by_name("NEWERA")
        row = ChannelLink.objects.create(
            name="Predates The Validator", link="acestream://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        ChannelLink.objects.filter(pk=row.pk).update(link="javascript:alert(1)")
        row.sources.add(source)

        command = Command()
        command.import_entries([("some name", None, ChannelLink.Quality.ANY, "javascript:alert(1)")], "NEWERA", False)

        assert not ChannelLink.objects.filter(pk=row.pk).exists()


@pytest.mark.django_db
class TestAddLinkSourceOrigin:
    """`--file` and `--url` are the two ways in, and exactly one must be given."""

    def test_addlinksource_requires_an_origin(self):
        with pytest.raises(CommandError):
            call_command("addlinksource", "--source=newera")

    def test_addlinksource_rejects_both_origins(self, tmp_path):
        source_file = tmp_path / "newera.txt"
        source_file.write_text("", encoding="utf-8")

        with pytest.raises(CommandError):
            call_command("addlinksource", "--source=newera", f"--file={source_file}", f"--url={TOKYO_URL}")

    def test_addlinksource_reports_a_missing_file(self, tmp_path):
        with pytest.raises(CommandError, match="Could not read"):
            call_command("addlinksource", "--source=newera", f"--file={tmp_path / 'absent.txt'}")

    def test_addlinksource_rejects_a_non_http_url(self):
        with pytest.raises(CommandError, match="http"):
            call_command("addlinksource", "--source=tokyo", "--url=file:///etc/passwd")

    def test_addlinksource_reports_an_unreachable_url(self):
        with patch(
            "soccertime.management.commands._link_import_base.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            with pytest.raises(CommandError, match="Could not fetch"):
                call_command("addlinksource", "--source=tokyo", f"--url={TOKYO_URL}")

    def test_addlinksource_reports_an_http_error(self):
        Channel.objects.create(name="DAZN 1")

        with fetching(TOKYO_PLAYLIST, status=404):
            with pytest.raises(CommandError, match="Could not fetch"):
                call_command("addlinksource", "--source=tokyo", f"--url={TOKYO_URL}")

        assert ChannelLink.objects.count() == 0

    def test_addlinksource_newera_from_url(self):
        """Every source reads from a URL, not only the M3U one."""
        channel = Channel.objects.create(name="DAZN 1")

        body = "DAZN 1 FHD --> NEW ERA\nacestream://1234567890123456789012345678901234567890\n"
        with fetching(body):
            call_command("addlinksource", "--source=newera", f"--url={TOKYO_URL}")

        link = ChannelLink.objects.get(link="acestream://1234567890123456789012345678901234567890")
        assert channel.links.filter(pk=link.pk).exists()

    def test_addlinksource_decodes_a_charsetless_response_as_utf8(self):
        """`requests` falls back to ISO-8859-1 for text/* with no charset: names would be mojibake."""
        channel = Channel.objects.create(name="Gol Play")

        playlist = (
            '#EXTM3U\n#EXTINF:-1 group-title="ESPAÑA",Gol Play\nacestream://2222222222222222222222222222222222222222\n'
        )
        with fetching(playlist):
            call_command("addlinksource", "--source=tokyo", f"--url={TOKYO_URL}")

        link = ChannelLink.objects.get(link="acestream://2222222222222222222222222222222222222222")
        assert link.subcategory == "España"
        assert channel.links.filter(pk=link.pk).exists()

    def test_addlinksource_reads_a_file_with_a_byte_order_mark(self, tmp_path):
        """A list saved from a browser carries a BOM, which glues itself to the first name.

        Harmless in an M3U, whose first line is a comment; in the line-pair formats the
        first line is a channel name, and the marker made it match nothing.
        """
        channel = Channel.objects.create(name="DAZN 1")

        source_file = tmp_path / "newera.txt"
        source_file.write_text(
            "DAZN 1 FHD --> NEW ERA\nacestream://1111111111111111111111111111111111111111\n",
            encoding="utf-8-sig",
        )

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://1111111111111111111111111111111111111111")
        assert channel.links.filter(pk=link.pk).exists()


@pytest.mark.django_db
class TestAddLinkSourceTokyo:
    def test_addlinksource_tokyo_from_file(self, tmp_path):
        channel = Channel.objects.create(name="DAZN 1")

        source_file = tmp_path / "tokyo.m3u"
        source_file.write_text(TOKYO_PLAYLIST, encoding="utf-8")

        call_command("addlinksource", "--source=tokyo", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://1111111111111111111111111111111111111111")
        assert link.name == "Dazn 1"
        assert link.subcategory == "Deportes"
        assert link.quality == ChannelLink.Quality.FHD
        assert channel.links.filter(pk=link.pk).exists()
        assert link.sources.filter(name="TOKYO").exists()

    def test_addlinksource_tokyo_from_url(self):
        channel = Channel.objects.create(name="DAZN 1")

        with fetching(TOKYO_PLAYLIST) as fetch:
            call_command("addlinksource", "--source=tokyo", f"--url={TOKYO_URL}")

        fetch.assert_called_once()
        assert fetch.call_args.args[0] == TOKYO_URL

        link = ChannelLink.objects.get(link="acestream://1111111111111111111111111111111111111111")
        assert channel.links.filter(pk=link.pk).exists()
        assert ChannelLinkSource.objects.filter(name="TOKYO").exists()

    def test_addlinksource_tokyo_dry_run_saves_nothing(self, tmp_path):
        Channel.objects.create(name="DAZN 1")

        source_file = tmp_path / "tokyo.m3u"
        source_file.write_text(TOKYO_PLAYLIST, encoding="utf-8")

        call_command("addlinksource", "--source=tokyo", f"--file={source_file}", "--dry")

        assert ChannelLink.objects.count() == 0

    def test_addlinksource_tokyo_matches_a_spaceless_sport_tv(self, tmp_path):
        """The playlist writes "SPORT TV2"; the catalogue writes "Sport TV 2"."""
        sport_tv_2 = Channel.objects.create(name="Sport TV 2")
        sport_tv_1 = Channel.objects.create(name="Sport TV 1")

        source_file = tmp_path / "tokyo.m3u"
        source_file.write_text(
            '#EXTM3U\n#EXTINF:-1 group-title="PORTUGAL",SPORT TV2 FHD\n'
            "acestream://3333333333333333333333333333333333333333\n",
            encoding="utf-8",
        )

        call_command("addlinksource", "--source=tokyo", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://3333333333333333333333333333333333333333")
        assert sport_tv_2.links.filter(pk=link.pk).exists()
        assert not sport_tv_1.links.filter(pk=link.pk).exists()

    def test_addlinksource_tokyo_gol_tv_is_the_spanish_channel(self, tmp_path):
        """The playlist's "Gol TV" is Gol Televisión, not the South American GolTV.

        The playlist entry carries tvg-id="Gol" and a logo served from goltelevision.com,
        and the catalogue row named GolTV Play holds Campeonato Uruguayo fixtures.
        """
        gol = Channel.objects.create(name="GOL (Síguelo en directo)")
        goltv = Channel.objects.create(name="GolTV Play")
        golstadium = Channel.objects.create(name="GolStadium (acceder)")
        golf = Channel.objects.create(name="Movistar Golf 2 (M68)")

        source_file = tmp_path / "tokyo.m3u"
        source_file.write_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="Gol" group-title="DEPORTES",Gol TV 1080p *\n'
            "acestream://5555555555555555555555555555555555555555\n",
            encoding="utf-8",
        )

        call_command("addlinksource", "--source=tokyo", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://5555555555555555555555555555555555555555")
        assert gol.links.filter(pk=link.pk).exists()
        for other in (goltv, golstadium, golf):
            assert not other.links.filter(pk=link.pk).exists()

    def test_addlinksource_tokyo_keeps_a_quality_suffix_out_of_the_name(self, tmp_path):
        """A quality suffix must not be read as a Sport TV channel number."""
        sport_tv = Channel.objects.create(name="Sport TV")

        source_file = tmp_path / "tokyo.m3u"
        source_file.write_text(
            '#EXTM3U\n#EXTINF:-1 group-title="PORTUGAL",Sport TV 1080p\n'
            "acestream://4444444444444444444444444444444444444444\n",
            encoding="utf-8",
        )

        call_command("addlinksource", "--source=tokyo", f"--file={source_file}")

        link = ChannelLink.objects.get(link="acestream://4444444444444444444444444444444444444444")
        assert link.name == "Sport Tv"
        assert link.quality == ChannelLink.Quality.FHD
        assert sport_tv.links.filter(pk=link.pk).exists()
