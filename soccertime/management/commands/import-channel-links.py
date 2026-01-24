import logging
import re

from bs4 import BeautifulSoup
from django.core.cache import cache
from django.core.management.base import BaseCommand

from soccertime.management.commands.channel_matchers import CHANNEL_MATCHERS, get_category, get_quality
from soccertime.models import ChannelLink

logging.basicConfig(level=logging.DEBUG)


def save_channel_link(
    name,
    link,
    channel=None,
    source="OTHER",
    quality=None,
    category="category",
    subcategory=None,
):
    try:
        channel_link = ChannelLink.objects.get(link=link)
        if channel_link and channel_link.source != source:
            logging.debug(f"Link {channel_link.link} already found with source {channel_link.source}")
            return
        channel_link.name = name
        channel_link.category = category
        channel_link.subcategory = subcategory
        channel_link.quality = quality or ChannelLink.Quality.ANY
        channel_link.source = source
        channel_link.channel = channel
        channel_link.save()
    except ChannelLink.DoesNotExist:
        channel_link = ChannelLink.objects.update_or_create(
            name=name,
            category=category,
            subcategory=subcategory,
            quality=quality or ChannelLink.Quality.ANY,
            link=link,
            source=source,
            channel=channel,
        )
    return channel_link


def get_zeronet():
    links = {}
    with open("./zeronet.txt", encoding="utf-8") as fp:
        contents = fp.read()
    name = None
    for line in contents.split("\n"):
        if "acestream" in line and name:
            if name not in links:
                links[name] = []
            links[name].append(line.strip())
            continue
        name = line.strip().split(" -->")[0]
    return links


def get_liart():
    links = {}
    with open("./eventos-liart.html", encoding="utf-8") as fp:
        html = fp.read()
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    for link in table.find_all("a"):
        name = link.get_text(strip=True).split(" -->")[0]
        acestream = link["href"]
        if "acestream" in acestream:
            if name not in links:
                links[name] = []
            if acestream not in links[name]:
                links[name].append(acestream)
    return links


def get_elcano():
    playlist = []
    with open("./lista-ace.m3u", encoding="utf-8") as file:
        lines = [line.strip() for line in file if line.strip()]

    if not lines or not lines[0].startswith("#EXTM3U"):
        raise ValueError("Not a valid extended M3U file")

    track_info = None
    for line in lines[1:]:
        if line.startswith("#EXTINF:"):
            match = re.search(r"#EXTINF:(?P<duration>-?\d+)(?:\s+(?P<attrs>[^,]+))?,(?P<title>.+)$", line)
            if match:
                attrs = match.group("attrs") or ""
                track_info = {
                    "duration": match.group("duration"),
                    "title": match.group("title").strip().split(" -->")[0],
                    "file": None,
                    "tvg-id": None,
                    "tvg-logo": None,
                    "group-title": None,
                }

                attr_matches = re.findall(r'([-\w]+)="(.*?)"', attrs)
                for key, value in attr_matches:
                    track_info[key.lower()] = value

        elif not line.startswith("#") and track_info:
            track_info["file"] = line
            playlist.append(track_info)
            track_info = None

    links = {}
    for p in playlist:
        name = p["title"]
        if name not in links:
            links[name] = []
        links[name].append(p["file"])
    return links


class Command(BaseCommand):
    help = "Add channels' links"

    def add_arguments(self, parser):
        parser.add_argument("--source", type=str, required=True, choices=["ZERONET", "LIART", "ELCANO"])

    def handle(self, *args, **options):
        if options["source"] == "ELCANO":
            source_links = get_elcano()
        elif options["source"] == "LIART":
            source_links = get_liart()
        elif options["source"] == "ZERONET":
            source_links = get_zeronet()
        else:
            return
        for name, links in source_links.items():
            for channel_matcher in CHANNEL_MATCHERS:
                channel_match = channel_matcher(name)
                if not channel_match.channel:
                    continue
                for link in links:
                    save_channel_link(
                        name,
                        link,
                        channel_match.channel,
                        options["source"],
                        channel_match.quality,
                        channel_match.category,
                    )
                break
            else:
                for link in links:
                    save_channel_link(name, link, None, options["source"], get_quality(name), get_category(name))
        cache.clear()
