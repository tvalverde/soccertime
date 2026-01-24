import logging

from django.core.cache import cache
from django.core.management.base import BaseCommand

from soccertime.models import Channel, ChannelLink

logging.basicConfig(level=logging.INFO)

SOURCE = "OTHER"
CHANNEL_MAPPER = {
    "Esport3 (Cataluña)": "https://www.3cat.cat/3cat/directes/esport3/",
    "Barça One": "https://one.fcbarcelona.com/es/videos/category/18478-live-content",
    (
        "DAZN F1 (M69)",
        "DAZN F1 Multicamara (Fórmula 1)",
    ): "acestream://968627d24eec1c16b51d88e4a4a6c02211e3346e",
    (
        "DAZN F1 (M69)",
        "DAZN F1 UHD (Fórmula 1)",
    ): "acestream://6b94479c24898700089e6b87d28a3ccc72dc4041",
}


class Command(BaseCommand):
    help = "Add other links to channels"

    def handle(self, *args, **options):
        for name, link in CHANNEL_MAPPER.items():
            if isinstance(name, tuple):
                channel_name, link_name = name
            else:
                channel_name = name
                link_name = name
            try:
                channel = Channel.objects.get(name=channel_name)
                logging.debug(f"Channel found {channel_name}")
            except Channel.DoesNotExist:
                logging.error(f"Channel not found {channel_name}")
                continue
            try:
                channel_link = ChannelLink.objects.get(
                    link=link,
                    source=SOURCE,
                )
                channel_link.name = link_name
                channel_link.category = "category"
                channel_link.subcategory = None
                channel_link.quality = ChannelLink.Quality.ANY
                channel_link.source = SOURCE
                channel_link.channel = channel
                channel_link.save()
            except ChannelLink.DoesNotExist:
                ChannelLink.objects.update_or_create(
                    name=link_name,
                    category="category",
                    subcategory=None,
                    quality=ChannelLink.Quality.ANY,
                    link=link,
                    source=SOURCE,
                    channel=channel,
                )

        cache.clear()
