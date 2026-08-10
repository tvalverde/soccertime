import re
from collections.abc import Iterable
from typing import Any

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction

from soccertime.models import Channel, ChannelLink, ChannelLinkSource


def _named_exactly_or_bracketed(channel_name: str, wanted: str) -> bool:
    """The name itself, or the name followed by the operator's bracketed suffix."""
    lowered = channel_name.lower()
    return lowered == wanted or f"{wanted} (" in lowered


def _has_every_token(channel_name: str, tokens: Iterable[str]) -> bool:
    """All tokens present. Short ones must match as whole words: "la" is not "LaLiga"."""
    lowered = channel_name.lower()
    return all(
        re.search(rf"\b{re.escape(token)}\b", channel_name, re.IGNORECASE)
        if len(token) < 4
        else token.lower() in lowered
        for token in tokens
    )


def _carries_number(channel_name: str, number: str) -> bool:
    lowered = channel_name.lower()
    return f" {number}" in lowered or lowered.endswith(number) or f"{number} (" in lowered


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

        if name.startswith("liga de campeones"):
            name = "m+ " + name
        if name == "dazn pvv":
            name = "dazn"
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

        lowered = normalised.lower()
        parts = normalised.split(" ")
        suffix_num = parts[-1] if parts[-1].isdigit() else None
        base_tokens = [token for token in (parts[:-1] if suffix_num else parts) if len(token) >= 2]
        catalogue = self.channel_catalogue

        # A variant must not be absorbed by the generic DAZN channel.
        dazn_variant = " ".join(parts[:2]).lower() if parts[0].lower() == "dazn" and len(parts) >= 2 else None

        matches = [channel for channel in catalogue if _named_exactly_or_bracketed(channel.name, lowered)]

        if dazn_variant and not suffix_num and not matches:
            matches = [channel for channel in catalogue if channel.name.lower().startswith(dazn_variant)]

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
            matches = [channel for channel in matches if channel.name.lower().startswith(precise)]

        return matches

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def import_entries(
        self, entries: Iterable[tuple[str, str | None, "ChannelLink.Quality", str]], source_name: str, dry_run: bool
    ) -> None:
        """Persist (channel_name, subcategory, quality, link) tuples."""
        source_obj, _ = ChannelLinkSource.get_or_create_by_name(source_name)

        stats = {
            "channels_processed": 0,
            "new_links": 0,
            "updated_links": 0,
            "linked_links": 0,
            "channels_not_found": 0,
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

                channel_link, created = ChannelLink.objects.update_or_create(
                    link=link,
                    defaults={
                        "name": channel_name.title(),
                        "category": category,
                        "subcategory": subcategory.title() if subcategory else None,
                        "quality": quality,
                    },
                )

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

        if self.warnings:
            self.stdout.write("\nWARNINGS:")
            for w in self.warnings:
                self.stdout.write(f"- {w}")
