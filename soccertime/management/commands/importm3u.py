import re
from pathlib import Path

from soccertime.management.commands._link_import_base import BaseLinkImportCommand

EXTINF_RE = re.compile(
    r"^#EXTINF:\s*-?\d+(?:\.\d+)?"  # duration: -1, 0, 10.5
    r'(?P<attrs>(?:\s+[\w.-]+="[^"]*")*)'  # key="value" attribute pairs
    r"\s*,\s*(?P<name>.+?)\s*$"  # display name after the attributes comma
)
ATTR_RE = re.compile(r'([\w.-]+)="([^"]*)"')
MIRROR_SUFFIX_RE = re.compile(r"\s*\[\d+\]\s*$")  # "DAZN Mundial 1 [2]" -> "DAZN Mundial 1"
ACESTREAM_HASH_RE = re.compile(r"[0-9a-fA-F]{40}")


class Command(BaseLinkImportCommand):
    help = "Import acestream channel links from an M3U playlist file"

    def add_arguments(self, parser):
        parser.add_argument("--file", "-f", required=True, help="Input M3U file path")
        parser.add_argument("--source", "-s", help="Source name (default: uppercased file name stem)")
        parser.add_argument("--dry", action="store_true", help="Dry run without saving")

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse_m3u(self, filepath):
        """Parse an M3U playlist into (channel_name, subcategory, quality, link) tuples.

        Pairs each #EXTINF directive with the following URL line, tolerating blank
        lines and unrelated # directives (#EXTM3U, #EXTVLCOPT, ...). Only acestream
        links (or bare 40-hex hashes) are kept; anything else is skipped with a warning.
        The group-title attribute becomes the subcategory.
        """
        with open(filepath, encoding="utf-8") as f:
            lines = [line.strip() for line in f]

        entries = []
        pending = None

        for line in lines:
            if not line:
                continue

            if line.startswith("#EXTINF"):
                if pending:
                    self.warnings.append(f"EXTINF with no URL (skipped): {pending['name']}")
                match = EXTINF_RE.match(line)
                if not match:
                    self.warnings.append(f"Malformed EXTINF (skipped): {line}")
                    pending = None
                    continue
                attrs = dict(ATTR_RE.findall(match.group("attrs")))
                pending = {"name": match.group("name"), "group_title": attrs.get("group-title")}
                continue

            if line.startswith("#"):
                continue

            if pending is None:
                self.warnings.append(f"URL with no preceding EXTINF (skipped): {line}")
                continue

            if line.startswith("acestream://"):
                hash_part = line.removeprefix("acestream://")
                if not ACESTREAM_HASH_RE.fullmatch(hash_part):
                    self.warnings.append(f"Invalid hash (skipped): {line}")
                    pending = None
                    continue
                link = line
            elif ACESTREAM_HASH_RE.fullmatch(line):
                link = f"acestream://{line}"
            else:
                self.warnings.append(f"Non-acestream URL (skipped): {line}")
                pending = None
                continue

            raw_name = MIRROR_SUFFIX_RE.sub("", pending["name"])
            channel_name, quality = self.extract_name_parts(raw_name)
            subcategory = pending["group_title"] or None

            entries.append((channel_name, subcategory, quality, link))
            pending = None

        if pending:
            self.warnings.append(f"EXTINF with no URL (skipped): {pending['name']}")

        return entries

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        source_name = (options["source"] or Path(options["file"]).stem).upper()
        dry_run = options["dry"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN ==="))

        entries = self.parse_m3u(options["file"])
        self.import_entries(entries, source_name, dry_run)
