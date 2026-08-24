import re
from argparse import ArgumentParser
from collections.abc import Callable
from typing import Any

from django.core.management.base import CommandError

from soccertime.management.commands._link_import_base import BaseLinkImportCommand, ParsedEntry


class Command(BaseLinkImportCommand):
    help = "Import channel links from different sources, read from a file or a URL"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--source", "-s", required=True, choices=["newera", "elcano", "tokyo"], help="Source parser"
        )
        origin = parser.add_mutually_exclusive_group(required=True)
        origin.add_argument("--file", "-f", help="Input file path")
        origin.add_argument("--url", "-u", help="Input URL")
        parser.add_argument("--dry", action="store_true", help="Dry run without saving")

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse_newera(self, lines: list[str]) -> list[ParsedEntry]:
        """Parse the newera format: alternating NAME --> SUBCATEGORY and HASH lines.

        The right-hand side is the subcategory, usually the feed aggregated inside
        newera. Malformed lines and hashes are collected as warnings and skipped: only an
        unreadable input aborts the import.
        """
        lines = [line.strip() for line in lines if line.strip()]

        if len(lines) % 2 != 0:
            self.warnings.append("Odd number of lines in the newera file: the last one is ignored")
            lines = lines[:-1]

        entries = []
        for i in range(0, len(lines), 2):
            name_line = lines[i]
            link_line = lines[i + 1]
            if " --> " not in name_line:
                self.warnings.append(f"Malformed name line: {name_line}")
                continue
            raw_name, source_label = name_line.split(" --> ", 1)

            name_norm, quality = self.extract_name_parts(raw_name)
            subcategory = source_label.strip().lower() if source_label else None

            link = link_line

            if not link.startswith("acestream://"):
                link = f"acestream://{link}"
            hash_part = link.replace("acestream://", "")
            if not re.fullmatch(r"[0-9a-fA-F]{40}", hash_part):
                self.warnings.append(f"Invalid hash (skipped): {link_line}")
                continue

            entries.append((name_norm, subcategory, quality, link))
        return entries

    def parse_elcano(self, lines: list[str]) -> list[ParsedEntry]:
        """Parse elcano custom text format.

        Format:
        === CATEGORY ===

        Channel Name
        acestream://hash
        """
        lines = [line.strip() for line in lines if line.strip()]

        entries = []
        current_subcategory = None

        # Skip header metadata lines until we hit the first separator or category
        start_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("===") or line.startswith("====="):
                start_idx = i
                break

        lines = lines[start_idx:]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Category detection: === CATEGORY ===
            if line.startswith("===") and line.endswith("==="):
                # Clean === markers
                current_subcategory = line.replace("=", "").strip()
                i += 1
                continue

            # Separators
            if line.startswith("====="):
                i += 1
                continue

            # Assume line is Channel Name
            # Check if next line exists and looks like a link
            if i + 1 < len(lines):
                link_line = lines[i + 1]
                # Basic validation that next line is likely a link or hash
                is_link = link_line.startswith("acestream://") or re.fullmatch(r"[0-9a-fA-F]{40}", link_line)

                if is_link:
                    raw_name = line
                    link = link_line
                    if not link.startswith("acestream://"):
                        link = f"acestream://{link}"

                    # Extract details
                    channel_name, quality = self.extract_name_parts(raw_name)
                    # Use the section header as subcategory
                    subcategory = current_subcategory.title() if current_subcategory else None

                    entries.append((channel_name, subcategory, quality, link))
                    i += 2  # Skip name and link
                    continue

            # If not a valid pair, just skip this line (could be metadata or orphan)
            i += 1

        return entries

    def parse_tokyo(self, lines: list[str]) -> list[ParsedEntry]:
        """The tokyo source publishes a plain M3U playlist, so the shared parser is all it needs."""
        return self.parse_m3u(lines)

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------
    def handle(self, *args: Any, **options: Any) -> None:
        source = options["source"].upper()
        dry_run = options["dry"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN ==="))

        parser_map: dict[str, Callable[[list[str]], list[ParsedEntry]]] = {
            "NEWERA": self.parse_newera,
            "ELCANO": self.parse_elcano,
            "TOKYO": self.parse_tokyo,
        }
        parser = parser_map.get(source)
        if not parser:
            raise CommandError(f"Unsupported source {source}")

        lines = self.read_input_lines(file=options["file"], url=options["url"])
        entries = parser(lines)
        self.import_entries(entries, source, dry_run)
