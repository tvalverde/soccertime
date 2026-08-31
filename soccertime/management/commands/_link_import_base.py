import re
import unicodedata
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urlparse

import requests
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from soccertime.models import Channel, ChannelLink, ChannelLinkSource

EXTINF_RE = re.compile(
    r"^#EXTINF:\s*-?\d+(?:\.\d+)?"  # duration: -1, 0, 10.5
    r'(?P<attrs>(?:\s+[\w.-]+="[^"]*")*)'  # key="value" attribute pairs
    r"\s*,\s*(?P<name>.+?)\s*$"  # display name after the attributes comma
)
ATTR_RE = re.compile(r'([\w.-]+)="([^"]*)"')
MIRROR_SUFFIX_RE = re.compile(r"\s*\[\d+\]\s*$")  # "DAZN Mundial 1 [2]" -> "DAZN Mundial 1"
ACESTREAM_HASH_RE = re.compile(r"[0-9a-fA-F]{40}")

# Per read rather than for the whole transfer, matching the image downloader: these
# playlists are a few hundred kilobytes, so a server that has not answered in this long is
# not going to.
URL_FETCH_TIMEOUT = 30

REMOTE_SCHEMES = frozenset({"http", "https"})

# (channel_name, subcategory, quality, link) — what every parser produces and
# import_entries() consumes.
ParsedEntry = tuple[str, str | None, "ChannelLink.Quality", str]


class PendingEntry(TypedDict):
    """An #EXTINF directive waiting for the URL line that follows it."""

    name: str
    group_title: str | None


@lru_cache(maxsize=2048)
def fold(text: str) -> str:
    """Lower case and drop the diacritics, so a name can be compared to a catalogue entry.

    67 of the 568 channels in production carry an accent and the published lists usually
    do not: "Aragon TV" found no channel, and every link naming it was dropped. Only the
    comparison is folded — the name that reaches the database keeps its accents.

    Cached because the catalogue is asked about once per entry and never changes within a
    run, so the same few hundred names would otherwise be decomposed thousands of times.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _named_exactly_or_bracketed(channel_name: str, wanted: str) -> bool:
    """The name itself, or the name followed by the operator's bracketed suffix."""
    folded = fold(channel_name)
    return folded == wanted or f"{wanted} (" in folded


def _has_every_token(channel_name: str, tokens: Iterable[str]) -> bool:
    """All tokens present. Short ones must match as whole words: "la" is not "LaLiga"."""
    folded = fold(channel_name)
    return all(
        re.search(rf"\b{re.escape(fold(token))}\b", folded) if len(token) < 4 else fold(token) in folded
        for token in tokens
    )


def _carries_number(channel_name: str, number: str) -> bool:
    folded = fold(channel_name)
    return f" {number}" in folded or folded.endswith(number) or f"{number} (" in folded


def _mentions_number(channel_name: str, number: str) -> bool:
    return bool(re.search(rf"\b{number}\b", channel_name))


class BaseLinkImportCommand(BaseCommand):
    """Shared pipeline for commands that import acestream channel links.

    Subclasses parse their input format into (channel_name, subcategory,
    quality, link) tuples and delegate persistence to import_entries().
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Owned here because import_entries() reads it: leaving each subclass to create
        # it means a new one that forgets breaks the shared pipeline instead of its own.
        self.warnings: list[str] = []
        self._channel_catalogue: list[Channel] | None = None

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def read_input_lines(self, *, file: str | None = None, url: str | None = None) -> list[str]:
        """Read the input as lines, from a local path or an HTTP(S) URL.

        The URL is typed by the operator running the command rather than scraped, so it
        needs none of the address vetting `_image_download` does. Its body does need an
        explicit decode: `requests` falls back to ISO-8859-1 for a text/* response that
        declares no charset, which is exactly what a raw playlist is served as, and every
        accented channel name in it would arrive as mojibake and match nothing.
        """
        if url:
            if urlparse(url).scheme not in REMOTE_SCHEMES:
                raise CommandError(f"Only http(s) URLs can be fetched, got: {url}")
            try:
                response = requests.get(url, timeout=URL_FETCH_TIMEOUT)
                response.raise_for_status()
            except requests.RequestException as error:
                raise CommandError(f"Could not fetch {url}: {error}") from error
            return response.content.decode("utf-8-sig", errors="replace").splitlines()

        if not file:
            raise CommandError("Either --file or --url is required")

        try:
            return Path(file).read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeDecodeError) as error:
            raise CommandError(f"Could not read {file}: {error}") from error

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse_m3u(self, lines: Iterable[str]) -> list[ParsedEntry]:
        """Parse an M3U playlist into (channel_name, subcategory, quality, link) tuples.

        Pairs each #EXTINF directive with the following URL line, tolerating blank
        lines and unrelated # directives (#EXTM3U, #EXTVLCOPT, ...). Only acestream
        links (or bare 40-hex hashes) are kept; anything else is skipped with a warning.
        The group-title attribute becomes the subcategory.
        """
        entries: list[ParsedEntry] = []
        pending: PendingEntry | None = None

        for raw_line in lines:
            line = raw_line.strip()
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
    # Helpers
    # ------------------------------------------------------------------
    def fix_name(self, name: str) -> str:
        name = name.lower()
        # Strip trailing server/mirror markers: *, **, (*), (**), etc.
        name = re.sub(r"\s*\(\*+\)\s*$", "", name).strip()
        name = re.sub(r"\s+\*+$", "", name).strip()
        # Strip trailing locale/region suffixes: (ES), (PL), (DE), (UK), (RU), etc.
        name = re.sub(r"\s*\([a-z]{2,3}\)\s*$", "", name).strip()
        name = name.replace("la liga", "laliga")
        if "plus+" not in name:
            name = name.replace("movistar plus", "movistar plus+")

        # Use regex for "laliga 1" to avoid matching "laliga 1080p" -> "laliga080p"
        name = re.sub(r"\blaliga 1\b", "laliga", name)

        name = name.replace("movistar vamos", "m+ vamos")

        name = name.replace("movistar deportes", "m+ deportes")
        name = name.replace("movistar ellas", "m+ ellas vamos")
        # Dot-variant alias used by some sources: "M. Deportes" -> "M+ Deportes"
        name = re.sub(r"\bm\.\s+deportes\b", "m+ deportes", name)

        # Normalize ACB event aliases to DAZN Baloncesto numbering
        # Examples:
        # - "ACB EVENTO 01" -> "dazn baloncesto 1"
        # - "ACB EVENTO 01 720p" -> "dazn baloncesto 1" (quality tag present, use search not fullmatch)
        # - "DAZN ACB 2" -> "dazn baloncesto 2"
        acb_event_match = re.search(r"\bacb\s+evento\s+0*(\d+)\b", name)
        if acb_event_match:
            return f"dazn baloncesto {int(acb_event_match.group(1))}"

        dazn_acb_match = re.search(r"\bdazn\s+acb\s+0*(\d+)\b", name)
        if dazn_acb_match:
            return f"dazn baloncesto {int(dazn_acb_match.group(1))}"

        # "Eleven DAZN N" -> "dazn N"
        # Eleven Sports was the Portuguese/Belgian operator that rebranded DAZN channels.
        eleven_dazn_match = re.search(r"\beleven\s+dazn\s+(\d+)\b", name)
        if eleven_dazn_match:
            return f"dazn {int(eleven_dazn_match.group(1))}"

        # "NBA EVENTOS N" -> "nba league pass"
        if re.search(r"\bnba\s+eventos?\b", name):
            return "nba league pass"

        # "DAZN EVENTOS N" -> "dazn N"
        dazn_eventos_match = re.search(r"\bdazn\s+eventos?\s+(\d+)\b", name)
        if dazn_eventos_match:
            return f"dazn {int(dazn_eventos_match.group(1))}"

        # "Canal N (1RFEF) (SOLO EVENTOS)" -> "rfef tv"
        if re.search(r"1rfef", name):
            return "rfef tv"

        # "Canal de Tenis" -> "tennis channel"
        if re.search(r"\bcanal\s+de\s+tenis\b", name):
            return "tennis channel"

        # "Sky Sports LaLiga" -> "dazn laliga" (UK feed of same rights holder)
        if re.search(r"\bsky\s+sports?\s+laliga\b", name):
            return "dazn laliga"

        # "Gol TV" -> "gol", the Spanish channel: the lists carry tvg-id="Gol" and a logo
        # served from goltelevision.com. It is not "GolTV Play", which is the South
        # American network and whose events here are the Campeonato Uruguayo.
        name = re.sub(r"\bgol\s+tv\b", "gol", name)

        if name.startswith("liga de campeones"):
            name = "m+ " + name
        if name == "dazn pvv":
            name = "dazn"

        # "Sport TV2" -> "sport tv 2" (M3U sources omit the space)
        name = re.sub(r"\bsport\s*tv\s*(\d+)\b", r"sport tv \1", name)

        return name

    def extract_quality(self, name: str) -> tuple[str, "ChannelLink.Quality"]:
        """Extract quality tag from name (HD, FHD, 1080p, etc.) and return cleaned name + quality enum."""
        quality = ChannelLink.Quality.ANY

        # Regex matches quality tags surrounded by word boundaries or brackets
        # Order matters: longer matches first (e.g. 1080p before 1080 if we supported bare numbers, though here specific tags are safer)
        # We look for [TAG] or space+TAG+space/end
        pattern = re.compile(r"(?:^|\s+|\[)(4k|uhd|fhd|1080p?|hd|720p?|sd)p?(?:\]|$|\s+)", re.IGNORECASE)

        match = pattern.search(name)
        if match:
            tag = match.group(1).lower()

            # Remove the detected tag from the name to clean it up
            # We use the full match (including brackets/spaces) to replace
            name = name.replace(match.group(0).strip(), "").strip()
            # Clean up potential double spaces or empty brackets left behind
            name = re.sub(r"\s+", " ", name).replace("[]", "").strip()

            if tag in {"4k", "uhd"}:
                quality = ChannelLink.Quality.UHD
            elif tag in {"fhd", "1080p", "1080"}:
                quality = ChannelLink.Quality.FHD
            elif tag in {"hd", "720p", "720"}:
                quality = ChannelLink.Quality.HD
            elif tag == "sd":
                quality = ChannelLink.Quality.SD

        return name, quality

    def extract_name_parts(self, raw_name: str) -> tuple[str, "ChannelLink.Quality"]:
        # Normalise known aliases before anything else
        name_fixed = self.fix_name(raw_name)
        # Lower and normalize spaces
        name_norm = re.sub(r"\s+", " ", name_fixed).strip()
        name_norm, quality = self.extract_quality(name_norm)

        return name_norm, quality

    @property
    def channel_catalogue(self) -> list["Channel"]:
        """Every channel, read once per run.

        The importer asks about hundreds of names in a single pass and the answers cannot
        change while it runs, so the whole table is worth one query rather than three per
        entry. These commands are one-shot processes; the snapshot cannot go stale.
        """
        if self._channel_catalogue is None:
            self._channel_catalogue = list(Channel.objects.all())
        return self._channel_catalogue

    def match_channels(self, channel_name: str) -> list["Channel"]:
        """Match channels, preferring a numeric suffix and falling back to tokens.

        Tried in order, each step only if the previous found nothing:

        1. the name exactly, or followed by a bracketed operator suffix
        2. for a DAZN variant without a number, the variant as a prefix
        3. with a trailing number, channels carrying that number and every base token;
           for the number 1, the same channels without any number, since sources write
           "DAZN LaLiga 1" for what the database calls "DAZN LaLiga"
        4. every token, in any position

        A name under four characters with no number stops after step 2: a two-letter
        token would otherwise pull in a large share of the table.
        """
        normalised = re.sub(r"\s+", " ", channel_name).strip()
        if not normalised:
            # An empty name identifies nothing, and step 1 would read it as "any channel
            # with a bracketed suffix" — 34 of them in production. Reachable: `fix_name`
            # reduces a name that is only a mirror marker, "(*)" or "(**)", to empty.
            return []

        folded = fold(normalised)
        parts = normalised.split(" ")
        suffix_num = parts[-1] if parts[-1].isdigit() else None
        base_tokens = [token for token in (parts[:-1] if suffix_num else parts) if len(token) >= 2]
        catalogue = self.channel_catalogue

        # A variant must not be absorbed by the generic DAZN channel.
        dazn_variant = fold(" ".join(parts[:2])) if parts[0].lower() == "dazn" and len(parts) >= 2 else None

        matches = [channel for channel in catalogue if _named_exactly_or_bracketed(channel.name, folded)]

        if dazn_variant and not suffix_num and not matches:
            matches = [channel for channel in catalogue if fold(channel.name).startswith(dazn_variant)]

        if len(normalised) < 4 and not suffix_num:
            return matches

        if not matches and suffix_num:
            strict = [
                channel
                for channel in catalogue
                if _carries_number(channel.name, suffix_num) and _has_every_token(channel.name, base_tokens)
            ]
            if strict:
                matches = strict
            elif suffix_num == "1":
                matches = [
                    channel
                    for channel in catalogue
                    if _has_every_token(channel.name, base_tokens) and not re.search(r"\b[2-9]\b", channel.name)
                ]

        if not matches:
            tokens = [token for token in base_tokens if not token.isnumeric()]
            if suffix_num:
                tokens.append(suffix_num)
            if tokens:
                matches = [channel for channel in catalogue if _has_every_token(channel.name, tokens)]
                if suffix_num:
                    # Channels naming the number outright come first; the sort is stable,
                    # so the rest keep the catalogue's alphabetical order.
                    matches.sort(key=lambda channel: 0 if _mentions_number(channel.name, suffix_num) else 1)

        if dazn_variant:
            precise = dazn_variant
            if suffix_num and suffix_num != "1" and not dazn_variant.endswith(f" {suffix_num}"):
                precise = f"{dazn_variant} {suffix_num}"
            matches = [channel for channel in matches if fold(channel.name).startswith(precise)]

        return matches

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def import_entries(self, entries: Iterable[ParsedEntry], source_name: str, dry_run: bool) -> None:
        """Persist (channel_name, subcategory, quality, link) tuples."""
        source_obj, _ = ChannelLinkSource.get_or_create_by_name(source_name)

        stats = {
            "channels_processed": 0,
            "new_links": 0,
            "updated_links": 0,
            "linked_links": 0,
            "channels_not_found": 0,
            "rejected_links": 0,
        }

        with transaction.atomic():
            for channel_name, subcategory, quality, link in entries:
                stats["channels_processed"] += 1

                channels = self.match_channels(channel_name)
                if not channels:
                    self.warnings.append(f"Channel not found: {channel_name}")
                    stats["channels_not_found"] += 1
                    continue

                category = re.sub(r" \d+", "", channel_name).title()

                defaults: dict[str, Any] = {
                    "name": channel_name.title(),
                    "category": category,
                    "subcategory": subcategory.title() if subcategory else None,
                }
                # ANY means the entry carries no tag, not that the quality is unknown to
                # everyone: a later list naming the same hash untagged must not erase what
                # an earlier one recorded. A link being created still gets the model's
                # default, and an explicit tag still replaces the stored one.
                if quality != ChannelLink.Quality.ANY:
                    defaults["quality"] = quality

                try:
                    channel_link, created = ChannelLink.objects.update_or_create(link=link, defaults=defaults)
                except ValidationError:
                    # These files come from outside the project, so one unusable entry
                    # must be reported and stepped over rather than abandoning the
                    # import, exactly as an unreachable image is during a scrape.
                    self.warnings.append(f"Rejected link with a disallowed scheme for {channel_name}: {link[:60]}")
                    stats["rejected_links"] += 1
                    continue

                if not dry_run:
                    channel_link.sources.add(source_obj)

                if created:
                    stats["new_links"] += 1
                    self.stdout.write(self.style.SUCCESS(f"  New: {link[:50]}..."))
                else:
                    stats["updated_links"] += 1
                    self.stdout.write(f"  Updated: {link[:50]}...")

                # Strategy: Match multiple channels but filter out restrictive types (e.g. BAR)
                # if the link doesn't explicitly ask for them.
                # This allows "LA 2" to match "La 2 TVE" AND "La 2 Cat",
                # but prevents "DAZN 1" from matching "DAZN 1 Bar".

                target_channels = channels

                for channel in target_channels:
                    # Safety: Avoid associating residential links to Horeca/Bar channels
                    # unless the link name explicitly says "BAR".
                    if "bar" in channel.name.lower() and "bar" not in channel_name.lower():
                        continue

                    if channel.links.filter(link=channel_link.link).exists():
                        self.warnings.append(f"Already present in {channel.name}: {link[:40]}...")
                        continue
                    if not dry_run:
                        channel.links.add(channel_link)
                    stats["linked_links"] += 1
                    self.stdout.write(f"  Linked to: {channel.name}")

            if dry_run:
                # Everything above ran against the database so the counts are real; the
                # rollback undoes it on the way out, with no exception to catch.
                transaction.set_rollback(True)

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run finished - nothing was saved"))

        if not dry_run:
            cache.clear()

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 50)
        self.stdout.write(f"Channels processed:   {stats['channels_processed']}")
        self.stdout.write(f"New links:            {stats['new_links']}")
        self.stdout.write(f"Updated links:        {stats['updated_links']}")
        self.stdout.write(f"Links linked:         {stats['linked_links']}")
        self.stdout.write(f"Channels not found:   {stats['channels_not_found']}")
        if stats["rejected_links"]:
            self.stdout.write(self.style.ERROR(f"Rejected links:       {stats['rejected_links']}"))

        if self.warnings:
            self.stdout.write("\nWARNINGS:")
            for w in self.warnings:
                self.stdout.write(f"- {w}")
