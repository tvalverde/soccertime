"""Characterization tests for `BaseLinkImportCommand.match_channels`.

This is the logic that decides which channel a scraped link is attached to. A mistake
here does not raise: it silently points a stream at the wrong channel, which is why the
behaviour is pinned down here in detail before the implementation is touched.

Every expectation below was verified against the current implementation. Where the
behaviour looks surprising, the test says so rather than hiding it.
"""

import pytest

from soccertime.management.commands._link_import_base import BaseLinkImportCommand
from soccertime.models import Channel

CHANNEL_NAMES = [
    "DAZN",
    "DAZN 1 (M70 O113)",
    "DAZN 2",
    "DAZN LaLiga",
    "DAZN LaLiga 2",
    "DAZN Baloncesto 1",
    "DAZN Baloncesto 2",
    "DAZN F1",
    "M+ LaLiga",
    "M+ LaLiga 2",
    "M+ Vamos",
    "La 1 TVE",
    "La 2 TVE",
    "LaLiga TV Bar",
    "Canal 5 MX",
    "Canal Sur",
    "Movistar Plus+",
    "TV",
    "Esport3 (Cataluña)",
    "Aragón TV",
]


@pytest.fixture
def channels(db):
    for name in CHANNEL_NAMES:
        Channel.objects.create(name=name)


@pytest.fixture
def match():
    command = BaseLinkImportCommand()

    def _match(name):
        return sorted(channel.name for channel in command.match_channels(name))

    return _match


@pytest.mark.django_db
class TestExactAndParenthesised:
    """The first attempt: an exact name, or the name followed by a parenthesised suffix."""

    def test_exact_name(self, channels, match):
        assert match("DAZN LaLiga") == ["DAZN LaLiga"]

    def test_is_case_insensitive(self, channels, match):
        assert match("dazn laliga") == ["DAZN LaLiga"]

    def test_matches_a_parenthesised_variant(self, channels, match):
        """Sources name a channel plainly; the database carries the operator's suffix."""
        assert match("DAZN 1") == ["DAZN 1 (M70 O113)"]

    def test_surrounding_and_repeated_whitespace_is_normalised(self, channels, match):
        assert match("  DAZN   LaLiga  ") == ["DAZN LaLiga"]

    def test_an_exact_hit_does_not_drag_in_the_wider_family(self, channels, match):
        """ "DAZN LaLiga" must not also bring "DAZN LaLiga 2"."""
        assert match("DAZN LaLiga") == ["DAZN LaLiga"]


@pytest.mark.django_db
class TestShortNames:
    """Names under four characters with no number only try exact and parenthesised.

    A two-letter token in the fallback would match a large share of the table.
    """

    def test_a_short_name_still_matches_exactly(self, channels, match):
        assert match("TV") == ["TV"]

    def test_a_short_name_with_no_exact_hit_matches_nothing(self, channels, match):
        assert match("M+") == []

    def test_a_short_name_does_not_reach_the_token_fallback(self, channels, match):
        """ "Sur" would otherwise pull in "Canal Sur"."""
        assert match("Sur") == []

    def test_a_number_lifts_the_short_name_restriction(self, channels, match):
        """With a numeric suffix the name is specific enough to keep going."""
        assert match("La 2") == ["La 2 TVE"]


@pytest.mark.django_db
class TestDaznVariants:
    """DAZN names carry a variant that generic DAZN channels must not absorb."""

    def test_a_variant_does_not_fall_back_to_the_generic_channel(self, channels, match):
        assert "DAZN" not in match("DAZN Baloncesto 1")

    def test_a_variant_without_a_number_matches_by_prefix(self, channels, match):
        assert match("DAZN LaLiga") == ["DAZN LaLiga"]

    def test_a_numbered_variant_keeps_its_number(self, channels, match):
        assert match("DAZN Baloncesto 2") == ["DAZN Baloncesto 2"]

    def test_the_number_is_not_appended_twice(self, channels, match):
        """For "DAZN 2" the variant phrase already ends in the number."""
        assert match("DAZN 2") == ["DAZN 2"]

    def test_a_lettered_variant(self, channels, match):
        assert match("DAZN F1") == ["DAZN F1"]

    def test_the_guard_only_applies_to_dazn(self, channels, match):
        assert match("M+ LaLiga") == ["M+ LaLiga"]


@pytest.mark.django_db
class TestNumericSuffix:
    def test_short_base_tokens_respect_word_boundaries(self, channels, match):
        """ "la 2" must not reach "LaLiga": the token is a word, not a prefix."""
        assert "LaLiga TV Bar" not in match("La 2")

    def test_suffix_one_falls_back_to_the_unnumbered_channel(self, channels, match):
        """Sources write "DAZN LaLiga 1" for a channel the database calls "DAZN LaLiga"."""
        assert "DAZN LaLiga" in match("DAZN LaLiga 1")

    def test_that_fallback_excludes_channels_carrying_another_number(self, channels, match):
        assert "DAZN LaLiga 2" not in match("DAZN LaLiga 1")

    def test_a_suffix_other_than_one_has_no_such_fallback(self, channels, match):
        assert match("M+ Vamos 3") == []


@pytest.mark.django_db
class TestTokenFallback:
    def test_every_token_is_required(self, channels, match):
        """ "canal 5 mx" must not absorb every channel beginning with "Canal"."""
        assert match("Canal 5 MX") == ["Canal 5 MX"]

    def test_a_partial_token_set_does_not_match(self, channels, match):
        assert "Canal Sur" not in match("Canal 5 MX")

    def test_matching_nothing_returns_empty(self, channels, match):
        assert match("Eurosport 1") == []


@pytest.mark.django_db
class TestMalformedInput:
    """None of these should raise: the importer feeds this whatever a playlist contains."""

    @pytest.mark.parametrize("name", ["", "   ", "\t\n"])
    def test_blank_names(self, channels, match, name):
        assert match(name) == []

    def test_a_bare_number(self, channels, match):
        """No base tokens at all, so nothing to require beyond the number itself."""
        assert isinstance(match("5"), list)

    @pytest.mark.parametrize("name", ["C+ (HD)", "a.b*c", "DAZN [1]", "x|y", "(((", "\\d+"])
    def test_regex_metacharacters_are_escaped(self, channels, match, name):
        """These reach `name__regex`; unescaped they would raise or match wildly."""
        assert isinstance(match(name), list)

    def test_a_very_long_name(self, channels, match):
        assert match("DAZN " + "x" * 500) == []

    def test_accented_characters(self, channels, match):
        assert match("Esport3") == ["Esport3 (Cataluña)"]

    @pytest.mark.parametrize("name", ["ARAGÓN TV", "aragón tv", "Aragón TV"])
    def test_accents_fold_in_upper_case_too(self, channels, match, name):
        """Playlists shout their names, and SQLite only case-folds ASCII.

        Matching in Python fixes this: `iexact` never saw "ARAGÓN" as "Aragón", so those
        links were reported as belonging to no channel and dropped.
        """
        assert match(name) == ["Aragón TV"]

    def test_returns_channels_the_caller_can_iterate(self, channels):
        """A list, since the matching happens in memory: `import_entries` iterates it."""
        command = BaseLinkImportCommand()
        result = command.match_channels("DAZN LaLiga")

        assert [channel.name for channel in result] == ["DAZN LaLiga"]

    def test_reads_the_channel_table_once_however_many_names_it_is_asked(self, channels, django_assert_num_queries):
        """Three queries per entry was the cost this replaced."""
        command = BaseLinkImportCommand()

        with django_assert_num_queries(1):
            for name in ["DAZN LaLiga", "M+ Vamos", "Canal 5 MX", "La 2", "nada de nada"]:
                command.match_channels(name)

    def test_no_channels_at_all(self, db, match):
        assert match("DAZN LaLiga") == []


@pytest.mark.django_db
class TestBarChannels:
    """Bar feeds are filtered by the caller, not here; this pins where that line sits."""

    def test_a_bar_channel_can_be_returned(self, channels, match):
        assert "LaLiga TV Bar" in match("LaLiga TV Bar")
