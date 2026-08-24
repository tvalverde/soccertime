from argparse import ArgumentParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.core.management.base import CommandError

from soccertime.management.commands._link_import_base import BaseLinkImportCommand


class Command(BaseLinkImportCommand):
    help = "Import acestream channel links from an M3U playlist, read from a file or a URL"

    def add_arguments(self, parser: ArgumentParser) -> None:
        origin = parser.add_mutually_exclusive_group(required=True)
        origin.add_argument("--file", "-f", help="Input M3U file path")
        origin.add_argument("--url", "-u", help="Input M3U playlist URL")
        parser.add_argument("--source", "-s", help="Source name (default: uppercased file or URL name stem)")
        parser.add_argument("--dry", action="store_true", help="Dry run without saving")

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------
    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = options["dry"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN ==="))

        source_name = (options["source"] or self.derive_source_name(options)).upper()

        lines = self.read_input_lines(file=options["file"], url=options["url"])
        entries = self.parse_m3u(lines)
        self.import_entries(entries, source_name, dry_run)

    def derive_source_name(self, options: dict[str, Any]) -> str:
        """The playlist's own name, so an unnamed import is still attributable.

        A URL need not end in a file name — a raw endpoint can be a bare host or a
        directory — and an empty source name would silently create an unnamed
        ChannelLinkSource that nothing can tell apart from the next one.
        """
        origin = options["file"] or urlparse(options["url"]).path
        stem = Path(origin).stem
        if not stem:
            raise CommandError("Could not derive a source name from the URL: pass --source")
        return stem
