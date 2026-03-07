import pytest
from django.core.management import call_command

from soccertime.models import Channel, ChannelLink, ChannelLinkSource


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
