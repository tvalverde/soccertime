import re

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q


from soccertime.models import Channel, ChannelLink, ChannelLinkSource


class Command(BaseCommand):
    help = "Import channel links from different sources"

    def add_arguments(self, parser):
        parser.add_argument("--source", "-s", required=True, choices=["newera", "elcano"], help="Source parser")
        parser.add_argument("--file", "-f", required=True, help="Input file path")
        parser.add_argument("--dry", action="store_true", help="Dry run without saving")


    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse_newera(self, filepath):
        """Parse newera format: alternating lines NAME --> SUBCATEGORY and HASH.

        - Usa el lado derecho como subcategoría (ej: fuente agregada dentro de newera).
        - Valida hashes de 40 hex; si no, warning y salta.
        - Acumula warnings, no aborta salvo que no se pueda leer el archivo.
        """
        with open(filepath, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        if len(lines) % 2 != 0:
            self.warnings.append("Archivo newera con número impar de líneas: se ignora la última línea")
            lines = lines[:-1]

        entries = []
        for i in range(0, len(lines), 2):
            name_line = lines[i]
            link_line = lines[i + 1]
            if " --> " not in name_line:
                self.warnings.append(f"Línea de nombre inválida: {name_line}")
                continue
            raw_name, source_label = name_line.split(" --> ", 1)

            # Fix specific names and normalize
            name_fixed = self.fix_name(raw_name)
            name_norm = re.sub(r"\s+", " ", name_fixed).strip()
            
            name_norm, quality = self.extract_quality(name_norm)
            subcategory = source_label.strip().lower() if source_label else None





            link = link_line

            if not link.startswith("acestream://"):
                link = f"acestream://{link}"
            hash_part = link.replace("acestream://", "")
            if not re.fullmatch(r"[0-9a-fA-F]{40}", hash_part):
                self.warnings.append(f"Hash inválido (se omite): {link_line}")
                continue

            entries.append((name_norm, subcategory, quality, link))
        return entries



    def parse_elcano(self, filepath):
        """Parse elcano custom text format.
        
        Format:
        === CATEGORY ===
        
        Channel Name
        acestream://hash
        """
        with open(filepath, encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]

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
                link_line = lines[i+1]
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
                    i += 2 # Skip name and link
                    continue

            # If not a valid pair, just skip this line (could be metadata or orphan)
            i += 1

        return entries


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def fix_name(self, name):
        name = name.lower()
        name = name.replace("la liga", "laliga")
        if "plus+" not in name:
            name = name.replace("movistar plus", "movistar plus+")
        
        # Use regex for "laliga 1" to avoid matching "laliga 1080p" -> "laliga080p"
        name = re.sub(r"\blaliga 1\b", "laliga", name)
        
        name = name.replace("movistar vamos", "m+ vamos")

        name = name.replace("movistar deportes", "m+ deportes")
        name = name.replace("movistar ellas", "m+ ellas vamos")
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
        pattern = re.compile(r"(?:^|\s+|\[)(4k|uhd|fhd|1080p|1080|hd|720p|720|sd)(?:\]|$|\s+)", re.IGNORECASE)
        
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

        match = pattern.search(name)
        if match:
            tag = match.group(1).lower()
            name = pattern.sub("", name).strip()
            if tag in {"4k", "uhd"}:
                quality = ChannelLink.Quality.UHD
            elif tag == "fhd":
                quality = ChannelLink.Quality.FHD
            elif tag == "hd":
                quality = ChannelLink.Quality.HD
            elif tag == "sd":
                quality = ChannelLink.Quality.SD
        return name, quality

    def extract_name_parts(self, raw_name):
        # Fix specific names first
        name_fixed = self.fix_name(raw_name)
        # Lower and normalize spaces
        name_norm = re.sub(r"\s+", " ", name_fixed).strip()
        name_norm, quality = self.extract_quality(name_norm)

        return name_norm, quality


    def match_channels(self, channel_name):
        """Match channels with numeric suffix priority and token-based fallback.

        - Si el nombre es muy corto (<=4 chars o un solo token sin sufijo), sólo intenta match exacto/contenga.
        """
        channel_name_norm = re.sub(r"\s+", " ", channel_name).strip()
        parts = channel_name_norm.split(" ")
        suffix_num = parts[-1] if parts and parts[-1].isdigit() else None
        base_tokens = parts[:-1] if suffix_num else parts

        # Short name safety: strict match only if very short AND no numeric suffix to aid specificity
        is_short_and_unsafe = len(channel_name_norm) < 4 and not suffix_num

        # Exact or contains with parentheses
        channels = Channel.objects.filter(
            Q(name__iexact=channel_name_norm) | Q(name__icontains=f"{channel_name_norm} (")
        )

        if is_short_and_unsafe:
            return channels


        # Try numeric suffix combination
        if not channels.exists() and suffix_num:
            # 1. Try strict match including the number
            channels_strict = Channel.objects.filter(
                Q(name__icontains=f" {suffix_num}") | Q(name__iendswith=suffix_num) | Q(name__icontains=f"{suffix_num} (")
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
            tokens = [c for c in base_tokens if len(c) >= 3 and not c.isnumeric()]
            if suffix_num:
                tokens.append(suffix_num)
            if tokens:
                channels = Channel.objects.all()
                for cpart in tokens:
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

        return channels


    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        source = options["source"].upper()
        filepath = options["file"]
        dry_run = options["dry"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== MODO DRY RUN ==="))

        self.warnings = []

        parser_map = {
            "NEWERA": self.parse_newera,
            "ELCANO": self.parse_elcano,
        }
        parser = parser_map.get(source)
        if not parser:
            raise CommandError(f"Unsupported source {source}")

        entries = parser(filepath)
        source_obj, _ = ChannelLinkSource.get_or_create_by_name(source)

        stats = {
            "canales_procesados": 0,
            "enlaces_nuevos": 0,
            "enlaces_actualizados": 0,
            "enlaces_asociados": 0,
            "errores_canal_no_encontrado": 0,
        }

        try:
            with transaction.atomic():
                for channel_name, subcategory, quality, link in entries:
                    stats["canales_procesados"] += 1

                    channels = self.match_channels(channel_name)
                    if not channels.exists():




                        self.warnings.append(f"Canal no encontrado: {channel_name}")
                        stats["errores_canal_no_encontrado"] += 1
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
                        stats["enlaces_nuevos"] += 1
                        self.stdout.write(self.style.SUCCESS(f"  Nuevo: {link[:50]}..."))
                    else:
                        stats["enlaces_actualizados"] += 1
                        self.stdout.write(f"  Actualizado: {link[:50]}...")

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
                            self.warnings.append(
                                f"Ya existe en {channel.name}: {channel_link.link[:40]}..."
                            )
                            continue
                        if not dry_run:
                            channel.links.add(channel_link)
                        stats["enlaces_asociados"] += 1
                        self.stdout.write(f"  Asociado a: {channel.name}")

                if dry_run:
                    raise transaction.TransactionManagementError("Dry run - rollback")

        except transaction.TransactionManagementError:
            if dry_run:
                self.stdout.write(self.style.WARNING("\nDry run completado - no se guardaron cambios"))
            else:
                raise

        if not dry_run:
            cache.clear()

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("RESUMEN"))
        self.stdout.write("=" * 50)
        self.stdout.write(f"Canales procesados:      {stats['canales_procesados']}")
        self.stdout.write(f"Enlaces nuevos:          {stats['enlaces_nuevos']}")
        self.stdout.write(f"Enlaces actualizados:    {stats['enlaces_actualizados']}")
        self.stdout.write(f"Enlaces asociados:       {stats['enlaces_asociados']}")
        self.stdout.write(f"Canales no encontrados:  {stats['errores_canal_no_encontrado']}")

        if self.warnings:
            self.stdout.write("\nWARNINGS:")
            for w in self.warnings:
                self.stdout.write(f"- {w}")
