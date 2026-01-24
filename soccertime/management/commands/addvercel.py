import logging
import re

from bs4 import BeautifulSoup
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db.models import Q

from soccertime.models import Channel, ChannelLink

logging.basicConfig(level=logging.INFO)

# https://eventos-liartvercelapp.vercel.app/
# https://ciriaco-liart.vercel.app/


class Command(BaseCommand):
    help = "Add vercel links to channels"

    def add_arguments(self, parser):
        parser.add_argument("--source-file", "-f", required=True)
        parser.add_argument("--dry", required=False, action="store_true")
        parser.add_argument("--source", choices=["liart", "ciriaco"], required=True)

    def fix_name(self, name):
        name = name.lower()
        name = name.replace("m deportes", "m+ deportes")
        if "m+" not in name:
            name = name.replace("vamos", "m+ vamos")
        name = name.replace("esport 3", "esport3")
        return name

    def add_ciriaco(self, options):
        with open(options["source_file"], encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")
        classified_channels = {}
        suffix_pattern = re.compile(r"\s*(1080|720|New Era [ivcdl]+|Estable|new loop)$", re.IGNORECASE)
        tables = soup.find_all("table")

        for table in tables:
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if not cells:
                    continue

                channels_cell = cells[-1]
                acestream_links = channels_cell.find_all("a", href=re.compile(r"^acestream://"))

                for link in acestream_links:
                    full_channel_name = link.get_text(strip=True)
                    acestream_id = link["href"].strip()
                    base_channel_name = suffix_pattern.sub("", full_channel_name).strip()
                    base_channel_name = re.sub(r"\s+", " ", base_channel_name)
                    base_channel_name = self.fix_name(base_channel_name)
                    channel_list = classified_channels.setdefault(base_channel_name, [])
                    if acestream_id not in channel_list:
                        channel_list.append(acestream_id)

        return {channel: list(ids) for channel, ids in classified_channels.items()}

    def add_liart(self, options):
        with open(options["source_file"]) as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")
        classified_channels = {}

        table_body = soup.find("tbody")
        if table_body:
            rows = table_body.find_all("tr")

            for row in rows:
                canales_cell = row.find("td", class_="canales")
                if not canales_cell:
                    continue

                acestream_links = canales_cell.find_all("a", href=re.compile(r"^acestream://"))

                for link in acestream_links:
                    full_channel_name = link.get_text(strip=True)
                    acestream_id = link["href"].strip()
                    base_channel_name = re.sub(r"\s*\(\s*Op\d+\s*\).*$", "", full_channel_name).strip()
                    base_channel_name = self.fix_name(base_channel_name)

                    if base_channel_name not in classified_channels:
                        classified_channels[base_channel_name] = set()

                    classified_channels[base_channel_name].add(acestream_id)

        return {channel: sorted(ids) for channel, ids in classified_channels.items()}

    def handle(self, *args, **options):
        if options["source"] == "liart":
            final_channels_dict = self.add_liart(options)
        elif options["source"] == "ciriaco":
            final_channels_dict = self.add_ciriaco(options)
        else:
            raise Exception(f"Unknown source {options['source']}")

        logging.debug(f"channels found: {final_channels_dict}")

        for channel, links in final_channels_dict.items():
            try:
                channels = Channel.objects.filter(Q(name__iexact=channel) | Q(name__icontains=f"{channel} ("))
            except Channel.DoesNotExist:
                channels = Channel.objects
                for cpart in channel.split(" "):
                    channels = channels.filter(name__icontains=cpart)

            if channels.count() == 0:
                logging.error(f"No channel found for {channel}")
                continue

            logging.debug(f"Channels {channels} found for {channel}")

            channel_links = []

            for link in links:
                try:
                    channel_link = ChannelLink.objects.get(
                        link=link,
                        source=options["source"].upper(),
                    )
                    logging.debug(f"Channel link found {channel_link} for {link}")
                    channel_link.name = channel.title()
                    channel_link.category = re.sub(r" \d+", "", channel).title()
                    channel_link.subcategory = None
                    channel_link.quality = ChannelLink.Quality.ANY
                    if not options["dry"]:
                        channel_link.save()
                    logging.debug(f"Update channel for link {link}")
                except ChannelLink.DoesNotExist:
                    channel_link = None
                    if not options["dry"]:
                        channel_link, _ = ChannelLink.objects.update_or_create(
                            name=channel.title(),
                            category=re.sub(r" \d+", "", channel).title(),
                            subcategory=None,
                            quality=ChannelLink.Quality.ANY,
                            link=link,
                            source=options["source"].upper(),
                        )
                    logging.info(f"Add channel for link {link}")

                if channel_link:
                    channel_links.append(channel_link)

            for channel_link in channel_links:
                for channel in channels:
                    if channel.links.filter(link=channel_link.link).count() > 0:
                        logging.warning(
                            f"Link {channel_link.link} ({channel_link.name}) already exists in channel {channel.id}"
                        )
                        continue

                    if not options["dry"]:
                        channel.links.add(channel_link)
                    logging.info(f"New link {channel_link.link} for channel {channel}")

        cache.clear()
