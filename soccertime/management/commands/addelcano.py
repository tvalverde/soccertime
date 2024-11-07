import logging
import re

from django.core.cache import cache
from django.core.management.base import BaseCommand

from soccertime.models import ChannelLink, Channel

logging.basicConfig(level=logging.INFO)

SOURCE = "ELCANO"
LINKS = {
    "#Ellas": [
        {
            "multiaudio": False,
            "name": "#Ellas 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://d8c2ed470e847154a88f011137cc206319f6bed5",
        }
    ],
    "#Vamos": [
        {
            "multiaudio": False,
            "name": "#Vamos 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://d03c13b6723f66155d7a0df3692a3b073fe630f2",
        },
        {
            "multiaudio": False,
            "name": "#Vamos 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://12ba546d229bc39f01c3c18988a034b215fe6adb",
        },
    ],
    "Copa": [
        {
            "multiaudio": False,
            "name": "Copa 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://f6beccbc4eea4bc0cda43b3e8ac14790a98b61b4",
        },
        {
            "multiaudio": False,
            "name": "Copa 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://b51f2d9a15b6956a44385b6be531bcabeb099d9d",
        },
    ],
    "DAZN 1": [
        {
            "multiaudio": False,
            "name": "DAZN 1 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://7cf0086fa7d478f51dbba952865c79e66cb9add5",
        },
        {
            "multiaudio": False,
            "name": "DAZN 1 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://35c7f0c966ecde3390f4510bb4caded40018c07a",
        },
    ],
    "DAZN 2": [
        {
            "multiaudio": False,
            "name": "DAZN 2 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://ca923c9873fd206a41c1e83ff8fc40e3cf323c9a",
        },
        {
            "multiaudio": False,
            "name": "DAZN 2 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://a929eeec1268d69d1556a2e3ace793b2577d8810",
        },
    ],
    "DAZN 3": [
        {
            "multiaudio": False,
            "name": "DAZN 3 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://19cd05c7ae26f22737ae5728b571ca36abd8a2e8",
        }
    ],
    "DAZN 4": [
        {
            "multiaudio": False,
            "name": "DAZN 4 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://4e83f23945ab3e43982045f88ec31daaa4683102",
        }
    ],
    "DAZN F1": [
        {
            "multiaudio": False,
            "name": "DAZN F1 1080 (Fórmula 1)",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://d6281d4e6310269b416180442a470d23a4a99dc9",
        },
        {
            "multiaudio": False,
            "name": "DAZN F1 1080 (Fórmula 1)",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://2c6e4c897661e6b0257bfe931b66d20b2ec763b6",
        },
        {
            "multiaudio": False,
            "name": "DAZN F1 1080 (Fórmula 1)",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://71eef80158aa8b37f3dc59f6793c6696df9a2dfa",
        },
        {
            "multiaudio": False,
            "name": "DAZN F1 720 (Fórmula 1)",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://268289e7a3c5209960b53b4d43c8c65fab294b85",
        },
    ],
    "DAZN LaLiga": [
        {
            "multiaudio": True,
            "name": "DAZN LaLiga 1080 MultiAudio",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://110d441ddc9713a7452588770d2bc85504672f47",
        },
        {
            "multiaudio": True,
            "name": "DAZN LaLiga 1080 MultiAudio",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://ec29289b0b14756e686c03a501bae1efa05be70c",
        },
        {
            "multiaudio": True,
            "name": "DAZN LaLiga 1080 MultiAudio",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://6de4794cd02f88f14354b5996823413a59a1de0f",
        },
        {
            "multiaudio": False,
            "name": "DAZN LaLiga 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://8c8c1e047a1c5ed213ba74722a5345dc55c3c0eb",
        },
    ],
    "DAZN LaLiga 2": [
        {
            "multiaudio": True,
            "name": "DAZN LaLiga 2 1080 MultiAudio",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://97ba38d47680954be40e48bd8f43e17222fefecb",
        },
        {
            "multiaudio": True,
            "name": "DAZN LaLiga 2 720 MultiAudio",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://51dbbfb42f8091e4ea7a2186b566a40e780953d9",
        },
    ],
    "EuroSport 1": [
        {
            "multiaudio": False,
            "name": "EuroSport 1 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://5e4cd48c79f991fcbee2de8b9d30c4b16de3b952",
        },
        {
            "multiaudio": False,
            "name": "EuroSport 1 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://16ffa1713f42aa27317ee039a2bd0cdbc89a1580",
        },
    ],
    "EuroSport 2": [
        {
            "multiaudio": False,
            "name": "EuroSport 2 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://c373da9e901d414b7384e671112e64d5a2310c29",
        },
        {
            "multiaudio": False,
            "name": "EuroSport 2 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://98784fa0714190de289f42eb5b84e405df7e685a",
        },
    ],
    "La Liga BAR": [
        {
            "multiaudio": False,
            "name": "La Liga BAR 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://608b0faf7d3d25f6fe5dba13d5e4b4142949990e",
        },
        {
            "multiaudio": False,
            "name": "La Liga BAR 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://94d34491106e00394835c8cb68aa94481339b53f",
        },
    ],
    "La1": [
        {
            "multiaudio": False,
            "name": "La1",
            "quality": ChannelLink.Quality.ANY,
            "url": "acestream://b9a81ddb0cf98d9a5ae18ba2eef0ab094bd5d5b0",
        },
        {
            "multiaudio": False,
            "name": "La1 UHD",
            "quality": ChannelLink.Quality.UHD,
            "url": "acestream://4a714c436cb67d53cf197f9038239fddab2d8b20",
        },
    ],
    "LaLiga Smartbank": [
        {
            "multiaudio": False,
            "name": "LaLiga Smartbank 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://b2706a7ffbea236a3b398139a3a606ada664c0eb",
        },
        {
            "multiaudio": False,
            "name": "LaLiga Smartbank 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://121f719ebb94193c6086ef92865cf9b197750980",
        },
    ],
    "LaLiga Smartbank 2": [
        {
            "multiaudio": False,
            "name": "LaLiga Smartbank 2 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://0cfdfde1b70623b8c210b0f7301be2a87456481d",
        },
        {
            "multiaudio": False,
            "name": "LaLiga Smartbank 2 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://0a335406bad0b658aeddb2d38f8c0614b2e5623a",
        },
    ],
    "LaLiga Smartbank 3": [
        {
            "multiaudio": False,
            "name": "LaLiga Smartbank 3",
            "quality": ChannelLink.Quality.ANY,
            "url": "acestream://fefd45ed6ff415e05f1341b7d9da2988eacd13ea",
        }
    ],
    "M. Deportes": [
        {
            "multiaudio": False,
            "name": "M. Deportes 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://55d4602cb22b0d8a33c10c2c2f42dae64a9e8895",
        },
        {
            "multiaudio": False,
            "name": "M. Deportes 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://3a74d9869b13e763476800740c6625e715a39879",
        },
    ],
    "M. Deportes 2": [
        {
            "multiaudio": False,
            "name": "M. Deportes 2 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://639c561dd57fa3fc91fde715caeb696c5efb7ce7",
        }
    ],
    "M. Deportes 3": [
        {
            "multiaudio": False,
            "name": "M. Deportes 3 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://571bff4d12b1791eb99dbf20bec38e630693a6a3",
        }
    ],
    "M. Deportes 4": [
        {
            "multiaudio": False,
            "name": "M. Deportes 4 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://b4d1308a61e4caf8c06ac3d6ce89d165c015c2fb",
        }
    ],
    "M. Deportes 5": [
        {
            "multiaudio": False,
            "name": "M. Deportes 5 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://fcc0fd75bf1dba40b108fcf0d3514e0e549bfbac",
        }
    ],
    "M. Deportes 6": [
        {
            "multiaudio": False,
            "name": "M. Deportes 6 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://cc5782d37ae6b6e0bab396dd64074982d0879046",
        }
    ],
    "M. Deportes 7": [
        {
            "multiaudio": False,
            "name": "M. Deportes 7 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://070f82d6443a52962d6a2ed9954c979b29404932",
        }
    ],
    "M. Golf": [
        {
            "multiaudio": False,
            "name": "M. Golf 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://f41f1096862767289620be5bd85727f946a434db",
        }
    ],
    "M. Golf2": [
        {
            "multiaudio": False,
            "name": "M. Golf2 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://e258e75e0e802afa5fcc53d46b47d8801a254ad5",
        }
    ],
    "M. LaLiga": [
        {
            "multiaudio": False,
            "name": "M. LaLiga 1080P",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://94d34491106e00394835c8cb68aa94481339b53f",
        },
        {
            "multiaudio": True,
            "name": "M. LaLiga 1080 MultiAudio",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://d3de78aebe544611a2347f54d5796bd87f16c92d",
        },
        {
            "multiaudio": True,
            "name": "M. LaLiga 1080 MultiAudio",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://6d05b31e5e8fdae312fbd57897363a7b10ddb163",
        },
        {
            "multiaudio": False,
            "name": "M. LaLiga 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://1bc437bce57b4b0450f6d1f8d818b7e97000745e",
        },
    ],
    "M. LaLiga 2": [
        {
            "multiaudio": False,
            "name": "M. LaLiga 2 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://83c6c4942d69f4aa324aa746c5d7dbfd7d1572b3",
        },
        {
            "multiaudio": False,
            "name": "M. LaLiga 2 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://f31a586422c9244196c810c84b6c85da350318a5",
        },
    ],
    "M. LaLiga 3": [
        {
            "multiaudio": False,
            "name": "M. LaLiga 3 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://ebe14f1edeb49f2253e3b355a8beeadc9b4f0bc4",
        },
        {
            "multiaudio": False,
            "name": "M. LaLiga 3 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://835639b89db00cc0d94660da3c10b6e38bfbcdc1",
        },
    ],
    "M.L. Campeones": [
        {
            "multiaudio": True,
            "name": "M.L. Campeones 1080 MultiAudio",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://0a26e20f39845e928411e09a124374fccb6e1478",
        },
        {
            "multiaudio": True,
            "name": "M.L. Campeones 1080 MultiAudio",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://775abd8697715c48a357906d40734ccd2a10513c",
        },
        {
            "multiaudio": False,
            "name": "M.L. Campeones 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://8edb264520569b2280c5e86b2dc734e120032903",
        },
    ],
    "M.L. Campeones 10": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 10 SD",
            "quality": ChannelLink.Quality.SD,
            "url": "acestream://c056f9e180cd7d40963129a17ff54f4ee8259353",
        }
    ],
    "M.L. Campeones 11": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 11 SD",
            "quality": ChannelLink.Quality.SD,
            "url": "acestream://a12a16f74cf12799d4475ae867dc61eb60e1ba2e",
        }
    ],
    "M.L. Campeones 12": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 12 SD",
            "quality": ChannelLink.Quality.SD,
            "url": "acestream://df7d145fcaf0566db4098d2f10236185d92bc9fd",
        }
    ],
    "M.L. Campeones 13": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 13 SD",
            "quality": ChannelLink.Quality.SD,
            "url": "acestream://bdfe9ebe62d690c1b13eef4346d72e618cfbe804",
        }
    ],
    "M.L. Campeones 2": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 2 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://c070cdb701fc46bb79d17568d99fc64620443d63",
        },
        {
            "multiaudio": False,
            "name": "M.L. Campeones 2 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://abdf9058786a48623d0de51a3adb414ae10b6e72",
        },
    ],
    "M.L. Campeones 3": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 3 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://3618edda333dad5374ac2c801f5f14483934b97d",
        },
        {
            "multiaudio": False,
            "name": "M.L. Campeones 3 720",
            "quality": ChannelLink.Quality.HD,
            "url": "acestream://0b348cc1ae499e810729661878764a0fab88ab69",
        },
    ],
    "M.L. Campeones 4": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 4 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://65a18a6bd83918a9586b673fec12405aaf4e9f7d",
        }
    ],
    "M.L. Campeones 5": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 5 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://11744c25a594e17d587ed0871fe40ff21b4bd1e0",
        }
    ],
    "M.L. Campeones 6": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 6 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://fdda1f0dd8c33fbdc5a66ab98e291f570cae67cd",
        }
    ],
    "M.L. Campeones 7": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 7 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://b7f47db93dced60f54e8f89e2366ed061b534049",
        }
    ],
    "M.L. Campeones 8": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 8 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://d298c6e5c8be71f5995b45289c6388b225318b3c",
        }
    ],
    "M.L. Campeones 9": [
        {
            "multiaudio": False,
            "name": "M.L. Campeones 9 SD",
            "quality": ChannelLink.Quality.SD,
            "url": "acestream://2d7c4cfb3987b652a779afc894cca2fccbbacf21",
        }
    ],
    "M.Plus": [
        {
            "multiaudio": False,
            "name": "M.Plus 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://56ac8e227d526e722624675ccdd91b0cc850582f",
        }
    ],
    "PPVP 1": [
        {
            "multiaudio": False,
            "name": "PPVP 1",
            "quality": ChannelLink.Quality.ANY,
            "url": "acestream://6994af284ecab2996f9b140ef44b8da8bfee0006",
        }
    ],
    "PPVP 2": [
        {
            "multiaudio": False,
            "name": "PPVP 2",
            "quality": ChannelLink.Quality.ANY,
            "url": "acestream://7cf437be950f3525e735be57c63f7824cab822c9",
        }
    ],
    "PPVP 3": [
        {
            "multiaudio": False,
            "name": "PPVP 3",
            "quality": ChannelLink.Quality.ANY,
            "url": "acestream://ad6f4e8e329d6a97c7e7d7b0b8e5d04d8dd0bb48",
        }
    ],
    "PPVP 4": [
        {
            "multiaudio": False,
            "name": "PPVP 4",
            "quality": ChannelLink.Quality.ANY,
            "url": "acestream://7cf437be950f3525e735be57c63f7824cab822c9",
        }
    ],
    "tdp": [
        {
            "multiaudio": False,
            "name": "tdp 1080",
            "quality": ChannelLink.Quality.FHD,
            "url": "acestream://61b9b271c16f970aab43cb753c5f8be181dceece",
        }
    ],
}
CHANNEL_MAPPER = {
    'M+ Liga de Campeones': 'M.L. Campeones',
    'M+ Liga de Campeones 2': 'M.L. Campeones 2',
    'M+ Liga de Campeones 3': 'M.L. Campeones 3',
    'M+ Liga de Campeones 4': 'M.L. Campeones 4',
    'M+ Liga de Campeones 5': 'M.L. Campeones 5',
    'M+ Liga de Campeones 6': 'M.L. Campeones 6',
    'M+ Liga de Campeones 7': 'M.L. Campeones 7',
    'M+ Liga de Campeones 8': 'M.L. Campeones 8',
    'M+ Liga de Campeones 9': 'M.L. Campeones 9',
    'M+ Liga de Campeones 10': 'M.L. Campeones 10',
    'M+ Liga de Campeones 11': 'M.L. Campeones 11',
    'M+ Liga de Campeones 12': 'M.L. Campeones 12',
    'M+ Liga de Campeones 13': 'M.L. Campeones 13',
    'La 1 TVE': 'La1',
    'M+ Ellas Vamos': '#Ellas',
    'M+ Vamos': '#Vamos',
    'M+ Copa del Rey': 'Copa',
    'LaLiga TV Bar': 'La Liga BAR',
    'LALIGA TV Hypermotion': 'LaLiga Smartbank',
    'LALIGA TV Hypermotion 2': 'LaLiga Smartbank 2',
    'M+ Deportes': 'M. Deportes',
    'M+ Deportes 2': 'M. Deportes 2',
    'M+ Deportes 3': 'M. Deportes 3',
    'M+ Deportes 4': 'M. Deportes 4',
    'M+ Deportes 5': 'M. Deportes 5',
    'M+ Deportes 6': 'M. Deportes 6',
    'M+ Deportes 7': 'M. Deportes 7',
    'M+ Deportes 8': 'M. Deportes 8',
    'M+ LaLiga TV': 'M. LaLiga',
    'M+ LaLiga TV 2': 'M. LaLiga 2',
    'M+ LaLiga TV 3': 'M. LaLiga 3',
    'Movistar Plus+': 'M.Plus',
    'Teledeporte': 'tdp',
}


class Command(BaseCommand):
    help = "Add elcano links to channels"

    def handle(self, *args, **options):
        channels_links = {}
        for name, links in LINKS.items():
            for link in links:
                try:
                    channel_link = ChannelLink.objects.get(
                        link=link['url'],
                        source=SOURCE,
                    )
                    channel_link.name=link['name']
                    channel_link.category=re.sub(r' \d+', '', name)
                    channel_link.subcategory=None
                    channel_link.quality=link["quality"]
                    channel_link.save()
                except ChannelLink.DoesNotExist:
                    channel_link, _ = ChannelLink.objects.update_or_create(
                        name=link['name'],
                        category=re.sub(r' \d+', '', name),
                        subcategory=None,
                        quality=link["quality"],
                        link=link['url'],
                        source=SOURCE,
                    )
                if name not in channels_links:
                    channels_links[name] = []
                channels_links[name].append(channel_link)

        for channel in Channel.objects.all():
            try:
                found = channels_links[CHANNEL_MAPPER[channel.name.split(" (", 1)[0]]]
            except KeyError:
                found = False
            if not found:
                try:
                    found = channels_links[channel.name.split(" (", 1)[0]]
                except KeyError:
                    found = False
            if not found:
                logging.error(f"Channel not found {channel.name}")
                continue
            for item in found:
                if channel.links.filter(link=item.link).count() > 0:
                    logging.warning(f"Channel found {channel.name} with same link")
                    continue
                logging.debug(f"Channel found {channel.name}")
                item.channel = channel
                item.save()

        cache.clear()
