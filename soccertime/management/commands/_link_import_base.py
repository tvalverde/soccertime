import re

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from soccertime.models import Channel, ChannelLink, ChannelLinkSource


class BaseLinkImportCommand(BaseCommand):
    """Shared pipeline for commands that import acestream channel links.

    Subclasses parse their input format into (channel_name, subcategory,
    quality, link) tuples and delegate persistence to import_entries().
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def fix_name(self, name):
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

    def extract_quality(self, name):
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

    def extract_name_parts(self, raw_name):
        # Normalise known aliases before anything else
        name_fixed = self.fix_name(raw_name)
        # Lower and normalize spaces
        name_norm = re.sub(r"\s+", " ", name_fixed).strip()
        name_norm, quality = self.extract_quality(name_norm)

        return name_norm, quality

    def match_channels(self, channel_name):
        """Match channels, preferring a numeric suffix and falling back to tokens.

        A very short name with no numeric suffix only tries an exact or contains match:
        a two-letter token would otherwise pull in half the table.
        """
        channel_name_norm = re.sub(r"\s+", " ", channel_name).strip()
        parts = channel_name_norm.split(" ")
        suffix_num = parts[-1] if parts and parts[-1].isdigit() else None
        base_tokens = parts[:-1] if suffix_num else parts

        # Short name safety: strict match only if very short AND no numeric suffix to aid specificity
        is_short_and_unsafe = len(channel_name_norm) < 4 and not suffix_num

        # DAZN variant safety: when variant is present (e.g. dazn 1, dazn f1, dazn laliga),
        # don't let generic DAZN channels absorb those links.
        dazn_variant_phrase = None
        if parts and parts[0].lower() == "dazn" and len(parts) >= 2:
            dazn_variant_phrase = " ".join(parts[:2]).lower()

        # Exact or contains with parentheses
        channels = Channel.objects.filter(
            Q(name__iexact=channel_name_norm) | Q(name__icontains=f"{channel_name_norm} (")
        )

        # Only use the broad dazn_variant_phrase fallback when there is no numeric suffix;
        # if there IS a suffix, let the numeric suffix logic below handle precise selection.
        if dazn_variant_phrase and not suffix_num and not channels.exists():
            channels = Channel.objects.filter(name__istartswith=dazn_variant_phrase)

        if is_short_and_unsafe:
            return channels

        # Try numeric suffix combination
        if not channels.exists() and suffix_num:
            # 1. Try strict match including the number
            channels_strict = Channel.objects.filter(
                Q(name__icontains=f" {suffix_num}")
                | Q(name__iendswith=suffix_num)
                | Q(name__icontains=f"{suffix_num} (")
            )
            for cpart in base_tokens:
                if len(cpart) >= 2:
                    # Use regex word boundary for short tokens to avoid "la" matching "laliga"
                    if len(cpart) < 4:
                        channels_strict = channels_strict.filter(name__regex=rf"(?i)\b{re.escape(cpart)}\b")
                    else:
                        channels_strict = channels_strict.filter(name__icontains=cpart)

            if channels_strict.exists():
                channels = channels_strict

            # 2. Special case: If suffix is '1' and strict match failed, try matching without the number
            #    (e.g., "DAZN LaLiga 1" -> "DAZN LaLiga")
            elif suffix_num == "1":
                channels_no_num = Channel.objects.all()
                for cpart in base_tokens:
                    if len(cpart) >= 2:
                        if len(cpart) < 4:
                            channels_no_num = channels_no_num.filter(name__regex=rf"(?i)\b{re.escape(cpart)}\b")
                        else:
                            channels_no_num = channels_no_num.filter(name__icontains=cpart)

                # Exclude channels that explicitly have other numbers (2, 3, etc.) to be safe
                channels = channels_no_num.exclude(name__regex=r"\b[2-9]\b")

        # Token fallback
        if not channels.exists():
            tokens = [c for c in base_tokens if len(c) >= 2 and not c.isnumeric()]
            if suffix_num:
                tokens.append(suffix_num)
            if tokens:
                channels = Channel.objects.all()
                for cpart in tokens:
                    # Require ALL tokens, using word boundaries for short ones, so a
                    # generic leading token can't absorb unrelated channels
                    # (e.g. "canal 5 mx" must not match every "Canal *" channel).
                    if len(cpart) < 4:
                        channels = channels.filter(name__regex=rf"(?i)\b{re.escape(cpart)}\b")
                    else:
                        channels = channels.filter(name__icontains=cpart)
                if suffix_num:
                    from django.db import models

                    channels = channels.order_by(
                        models.Case(
                            models.When(name__regex=rf"\b{suffix_num}\b", then=0),
                            default=1,
                            output_field=models.IntegerField(),
                        )
                    )
            else:
                channels = Channel.objects.none()

        if dazn_variant_phrase:
            # Build a precise startswith phrase. When suffix_num is present and > 1,
            # include the number — but only if dazn_variant_phrase doesn't already end
            # with it (e.g. "dazn 2" already contains the number; "dazn baloncesto" does not).
            if suffix_num and suffix_num != "1" and not dazn_variant_phrase.endswith(f" {suffix_num}"):
                precise_phrase = f"{dazn_variant_phrase} {suffix_num}"
            else:
                precise_phrase = dazn_variant_phrase
            channels = channels.filter(name__istartswith=precise_phrase)

        return channels

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def import_entries(self, entries, source_name, dry_run):
        """Persist (channel_name, subcategory, quality, link) tuples."""
        source_obj, _ = ChannelLinkSource.get_or_create_by_name(source_name)

        stats = {
            "channels_processed": 0,
            "new_links": 0,
            "updated_links": 0,
            "linked_links": 0,
            "channels_not_found": 0,
        }

        try:
            with transaction.atomic():
                for channel_name, subcategory, quality, link in entries:
                    stats["channels_processed"] += 1

                    channels = self.match_channels(channel_name)
                    if not channels.exists():
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
                            self.warnings.append(f"Already present in {channel.name}: {channel_link.link[:40]}...")
                            continue
                        if not dry_run:
                            channel.links.add(channel_link)
                        stats["linked_links"] += 1
                        self.stdout.write(f"  Linked to: {channel.name}")

                if dry_run:
                    raise transaction.TransactionManagementError("Dry run - rollback")

        except transaction.TransactionManagementError:
            if dry_run:
                self.stdout.write(self.style.WARNING("\nDry run finished - nothing was saved"))
            else:
                raise

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
