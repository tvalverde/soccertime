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

    def test_addlinksource_fix_name_logic(self, tmp_path):
        """Test specific fix_name replacements (e.g. Movistar -> M+)."""
        channel = Channel.objects.create(name="M+ Vamos")

        source_file = tmp_path / "test_fixname.txt"
        source_content = """MOVISTAR VAMOS FHD --> NEW ERA
acestream://1111111111111111111111111111111111111111
"""
        source_file.write_text(source_content, encoding="utf-8")

        call_command("addlinksource", "--source=newera", f"--file={source_file}")

        # Should match "M+ Vamos" because "MOVISTAR VAMOS" is fixed to "m+ vamos"
        link = ChannelLink.objects.first()
        assert channel.links.filter(pk=link.pk).exists()
