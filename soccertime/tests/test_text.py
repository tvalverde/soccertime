"""Tests for the shared text helpers."""

from soccertime.text import fold


class TestFold:
    def test_lowercases_and_drops_diacritics(self):
        assert fold("Fútbol") == "futbol"

    def test_leaves_plain_ascii_alone(self):
        assert fold("dazn 1") == "dazn 1"

    def test_importer_uses_the_shared_fold(self):
        """The channels page filter matches what the importer folded; they must not drift."""
        from soccertime.management.commands import _link_import_base

        assert _link_import_base.fold is fold
