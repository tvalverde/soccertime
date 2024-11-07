import re
from django.db import transaction
from django.core.cache import cache
from django.db.models import Q
from django.core.management.base import BaseCommand
from soccertime.models import ChannelLink, Channel

DEFAULT_SOURCE = "newera"


class Command(BaseCommand):
    help = "Add new era links to channels"

    def add_arguments(self, parser):
        parser.add_argument("--source-file", "-f", required=True)
        parser.add_argument(
            "--source", "-s", default=DEFAULT_SOURCE, help="Source name for the links"
        )
        parser.add_argument(
            "--dry", required=False, action="store_true", help="Dry run without saving"
        )

    def fix_name(self, name):
        name = name.lower()
        name = name.replace("la liga", "laliga")
        if "plus+" not in name:
            name = name.replace("movistar plus", "movistar plus+")
        name = name.replace("laliga 1", "laliga")
        name = name.replace("movistar vamos", "m+ vamos")
        name = name.replace("movistar deportes", "m+ deportes")
        name = name.replace("movistar ellas", "m+ ellas vamos")
        if name == "dazn pvv":
            name = "dazn"
        return name

    def validate_acestream_hash(self, hash_str):
        """Valida que el hash sea un hash de acestream válido (40 caracteres hexadecimales)."""
        clean_hash = hash_str.replace("acestream://", "")
        return bool(re.match(r"^[a-f0-9]{40}$", clean_hash.lower()))

    def parse_name_line(self, line):
        """Parsea una línea de nombre y extrae canal y subcategoría.

        Returns:
            tuple: (nombre_canal, subcategoria) o (None, None) si el formato es inválido
        """
        if " --> " not in line:
            return None, None

        parts = line.split(" --> ")
        if len(parts) != 2:
            return None, None

        channel_name = self.fix_name(parts[0].strip())
        subcategory = parts[1].strip()

        return channel_name, subcategory

    def add_newera(self, options):
        """Lee el fichero y extrae los canales con sus enlaces.

        Returns:
            dict: {(nombre_canal, subcategoria): [links]}
        """
        with open(options["source_file"], "r", encoding="utf-8") as f:
            contents = f.read()

        # Filtrar líneas vacías
        lines = [line.strip() for line in contents.split("\n") if line.strip()]

        channels = {}
        errors = []

        # Procesar en chunks de 2 líneas
        for i in range(0, len(lines), 2):
            name_line = lines[i]

            # Verificar que existe la línea del link
            if i + 1 >= len(lines):
                errors.append(f"Línea {i+1}: '{name_line}' sin enlace asociado")
                continue

            link_line = lines[i + 1]

            # Parsear nombre y subcategoría
            channel_name, subcategory = self.parse_name_line(name_line)
            if not channel_name:
                errors.append(
                    f"Línea {i+1}: Formato inválido '{name_line}' (esperado: 'NOMBRE --> SUBCATEGORIA')"
                )
                continue

            # Validar hash de acestream
            if not self.validate_acestream_hash(link_line):
                errors.append(f"Línea {i+2}: Hash inválido '{link_line}'")
                continue

            # Añadir prefijo acestream:// si no lo tiene
            if not link_line.startswith("acestream://"):
                link_line = f"acestream://{link_line}"

            # Usar tupla (nombre, subcategoria) como clave
            key = (channel_name, subcategory)
            if key not in channels:
                channels[key] = []
            channels[key].append(link_line)

        # Mostrar errores de parsing
        for error in errors:
            self.stderr.write(self.style.WARNING(error))

        return channels, len(errors)

    def extract_quality(self, channel_name):
        """Extrae la calidad del nombre del canal.

        Returns:
            tuple: (nombre_sin_calidad, calidad)
        """
        quality = ChannelLink.Quality.ANY

        if channel_name.endswith(" hd"):
            channel_name = channel_name.replace(" hd", "")
            quality = ChannelLink.Quality.HD
        elif channel_name.endswith(" fhd"):
            channel_name = channel_name.replace(" fhd", "")
            quality = ChannelLink.Quality.FHD
        elif channel_name.endswith(" sd"):
            channel_name = channel_name.replace(" sd", "")
            quality = ChannelLink.Quality.SD

        return channel_name, quality

    def handle(self, *args, **options):
        source = options["source"].upper()
        dry_run = options["dry"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== MODO DRY RUN ==="))

        # Contadores para resumen
        stats = {
            "canales_procesados": 0,
            "enlaces_nuevos": 0,
            "enlaces_actualizados": 0,
            "enlaces_asociados": 0,
            "errores_canal_no_encontrado": 0,
            "errores_parsing": 0,
        }

        channels_dict, parsing_errors = self.add_newera(options)
        stats["errores_parsing"] = parsing_errors

        try:
            with transaction.atomic():
                for (raw_channel, subcategory), links in channels_dict.items():
                    stats["canales_procesados"] += 1

                    channel_name, quality = self.extract_quality(raw_channel)

                    # Buscar canales existentes
                    channels = Channel.objects.filter(
                        Q(name__iexact=channel_name)
                        | Q(name__icontains=f"{channel_name} (")
                    )

                    # Si no encuentra, buscar por partes del nombre
                    if not channels.exists():
                        channels = Channel.objects.all()
                        for cpart in channel_name.split(" "):
                            channels = channels.filter(name__icontains=cpart)

                    if not channels.exists():
                        self.stderr.write(
                            self.style.ERROR(f"Canal no encontrado: {channel_name}")
                        )
                        stats["errores_canal_no_encontrado"] += 1
                        continue

                    self.stdout.write(
                        f"Procesando: {channel_name} ({channels.count()} coincidencias)"
                    )

                    channel_links = []
                    category = re.sub(r" \d+", "", channel_name).title()

                    for link in links:
                        try:
                            # Intentar obtener enlace existente
                            channel_link = ChannelLink.objects.get(
                                link=link, source=source
                            )

                            # Actualizar datos
                            channel_link.name = channel_name.title()
                            channel_link.category = category
                            channel_link.subcategory = subcategory
                            channel_link.quality = quality

                            if not dry_run:
                                channel_link.save()

                            stats["enlaces_actualizados"] += 1
                            self.stdout.write(f"  Actualizado: {link[:50]}...")

                        except ChannelLink.DoesNotExist:
                            # Crear nuevo enlace
                            if not dry_run:
                                channel_link = ChannelLink.objects.create(
                                    name=channel_name.title(),
                                    category=category,
                                    subcategory=subcategory,
                                    quality=quality,
                                    link=link,
                                    source=source,
                                )
                            else:
                                channel_link = ChannelLink(
                                    name=channel_name.title(),
                                    category=category,
                                    subcategory=subcategory,
                                    quality=quality,
                                    link=link,
                                    source=source,
                                )

                            stats["enlaces_nuevos"] += 1
                            self.stdout.write(
                                self.style.SUCCESS(f"  Nuevo: {link[:50]}...")
                            )

                        channel_links.append(channel_link)

                    # Asociar enlaces a canales
                    for channel_link in channel_links:
                        for channel in channels:
                            if channel.links.filter(link=channel_link.link).exists():
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"  Ya existe en {channel.name}: {channel_link.link[:40]}..."
                                    )
                                )
                                continue

                            if not dry_run:
                                channel.links.add(channel_link)

                            stats["enlaces_asociados"] += 1
                            self.stdout.write(f"  Asociado a: {channel.name}")

                if dry_run:
                    # Rollback en dry run
                    raise transaction.TransactionManagementError("Dry run - rollback")

        except transaction.TransactionManagementError:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING("\nDry run completado - no se guardaron cambios")
                )
            else:
                raise

        # Limpiar caché solo si no es dry run
        if not dry_run:
            cache.clear()

        # Mostrar resumen
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("RESUMEN"))
        self.stdout.write("=" * 50)
        self.stdout.write(f"Canales procesados:      {stats['canales_procesados']}")
        self.stdout.write(f"Enlaces nuevos:          {stats['enlaces_nuevos']}")
        self.stdout.write(f"Enlaces actualizados:    {stats['enlaces_actualizados']}")
        self.stdout.write(f"Enlaces asociados:       {stats['enlaces_asociados']}")

        if stats["errores_parsing"] or stats["errores_canal_no_encontrado"]:
            self.stdout.write(
                self.style.ERROR(f"Errores de parsing:      {stats['errores_parsing']}")
            )
            self.stdout.write(
                self.style.ERROR(
                    f"Canales no encontrados:  {stats['errores_canal_no_encontrado']}"
                )
            )
