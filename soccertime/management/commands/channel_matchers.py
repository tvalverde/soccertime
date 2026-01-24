import re
from collections import namedtuple

from soccertime.models import Channel, ChannelLink

ChannelMatch = namedtuple(
    "ChannelMatch",
    ["channel", "quality", "category", "subcategory"],
    defaults=[None, ChannelLink.Quality.ANY, "category", None],
)


def get_quality(name):
    if "FHD" in name.upper() or "1080" in name:
        quality = ChannelLink.Quality.FHD
    elif "HD" in name.upper() or "720" in name:
        quality = ChannelLink.Quality.HD
    else:
        quality = ChannelLink.Quality.ANY
    return quality


def get_category(name):
    match = re.match(r"^(.*?)(?=\d|FHD|\(|HD)", name)
    return match.group(1) if match else "category"


def simple_match(match, name, channel):
    if not re.search(match, name, re.IGNORECASE):
        return ChannelMatch()
    return ChannelMatch(
        channel,
        get_quality(name),
        get_category(name),
    )


def direct_match(xname, name, ch_name):
    if name not in xname:
        return ChannelMatch()
    try:
        return ChannelMatch(
            Channel.objects.get(name=ch_name),
            get_quality(xname),
            get_category(name),
        )
    except Channel.DoesNotExist:
        pass
    return ChannelMatch()


def match_movistar_deportes(name):
    match = re.search(
        r"M(?:[+.])?\s*DEPORTES(?: (\d+))?(?: (FHD|HD))?(?: (\d+))?(?: \(\*\))?$",
        name,
        re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r"Movistar Deportes ?(\d+)?",
            name,
            re.IGNORECASE,
        )
        if not match:
            return ChannelMatch()
    number = match.group(1)
    try:
        return ChannelMatch(
            Channel.objects.get(name__startswith=(f"M+ Deportes {number} (" if number else "M+ Deportes (")),
            get_quality(name),
            get_category(name),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_dazn(name):
    match = re.search(r"DAZN\s*(\d+)\*?(?: FHD)?(?: \(SAT\))?(?: \(\*\))?$", name, re.IGNORECASE)
    if not match:
        match = re.search(r"Dazn (\d) (720|1080|FHD|HD)$", name, re.IGNORECASE)
        if not match:
            return ChannelMatch()
    number = match.group(1)
    try:
        return ChannelMatch(
            Channel.objects.get(name__startswith=(f"DAZN {number} (" if number else "DAZN (")),
            get_quality(name),
            get_category(name),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_dazn_bar(name):
    match = re.search(r"\s*DAZN (\d+) BAR FHD(?: \(\*\))?", name, re.IGNORECASE)
    if not match:
        return ChannelMatch()
    number = match.group(1) or "1"
    try:
        return ChannelMatch(
            Channel.objects.get(name__startswith=f"DAZN {number} Bar ("),
            get_quality(name),
            get_category(name),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_vamos(name):
    if "vamos" in name.lower() and "bar" not in name.lower() and "ellas" not in name.lower():
        return ChannelMatch(
            Channel.objects.get(name__startswith="M+ Vamos ("),
            get_quality(name),
            get_category(name),
        )
    return ChannelMatch()


def match_vamos_ellas(name):
    if "vamos" in name.lower() and "bar" not in name.lower() and "ellas" in name.lower():
        return ChannelMatch(
            Channel.objects.get(name__startswith="M+ Ellas Vamos ("),
            get_quality(name),
            get_category(name),
        )
    return ChannelMatch()


def match_eurosport(name):
    match = re.search(r"EUROSPORT(?: (\d+))?(?: FHD| HD)?", name, re.IGNORECASE)
    if not match:
        return ChannelMatch()
    number = match.group(1)
    if not number:
        number = "1"
    try:
        return ChannelMatch(
            Channel.objects.get(name__startswith=f"Eurosport {number}"),
            get_quality(name),
            get_category(name),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_dazn_f1(name):
    try:
        return simple_match(
            r"\s*DAZN (?:F1|FORMULA 1)(?: \d+)?(?: 1080| 720| FHD)?(?: \(.*?\))?",
            name,
            Channel.objects.get(name__startswith="DAZN F1 ("),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_copa_del_rey(name):
    try:
        return simple_match(
            r"\s*(M\+ SuperCopa del Rey FHD|Copa del Rey)",
            name,
            Channel.objects.get(name__startswith="M+ Copa del Rey ("),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_m_laliga(name):
    match = re.search(
        r"M\. LaLiga(?: (\d) )?(?:(1080P|1080 MultiAudio|1080|720))?",
        name,
        re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r"^Laliga TV( | \d|)?(720)?\(op\d+\)$",
            name,
            re.IGNORECASE,
        )
        if not match:
            return ChannelMatch()
    number = match.group(1)
    if number:
        number = number.strip()
    try:
        return ChannelMatch(
            Channel.objects.get(name__startswith=(f"M+ LaLiga TV {number} (" if number else "M+ LaLiga TV (")),
            get_quality(name),
            get_category(name),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_dazn_laliga(name):
    match = re.search(r"DAZN LaLiga(?: (\d) )?(?: (1080 MultiAudio|720))?", name, re.IGNORECASE)
    if not match:
        return ChannelMatch()
    number = match.group(1)
    if number:
        number = number.strip()
    try:
        return ChannelMatch(
            Channel.objects.get(name__startswith=(f"DAZN LaLiga {number} (" if number else "DAZN LaLiga (")),
            get_quality(name),
            get_category(name),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_hypermotion(name):
    match = re.search(r"LaLiga HYPERMOTION(?: (\d) )?(?:(1080|720))?", name, re.IGNORECASE)
    if not match:
        match = re.search(r"LaLiga TV Hypermotion(?: (\d))?", name, re.IGNORECASE)
        if not match:
            return ChannelMatch()
    number = match.group(1)
    if number:
        number = number.strip()
    try:
        return ChannelMatch(
            Channel.objects.get(
                name__startswith=(f"LALIGA TV Hypermotion {number} (" if number else "LALIGA TV Hypermotion (")
            ),
            get_quality(name),
            get_category(name),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_liga_campeones(name):
    match = re.search(
        r"M[+\.]?( LIGA DE|L\.)? CAMPEONES(?: (\d+))?(?: (FHD|SD))?(?: \(SAT\))?(?: \(\*\))?$",
        name,
        re.IGNORECASE,
    )
    if not match:
        return ChannelMatch()
    number = match.group(2)
    try:
        return ChannelMatch(
            Channel.objects.get(
                name__startswith=(f"M+ Liga de Campeones {number} (" if number else "M+ Liga de Campeones (")
            ),
            get_quality(name),
            get_category(name),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_gol_play(name):
    return direct_match(name, "Gol Play FHD", "GOL PLAY (")


def match_laliga_tv_bar(name):
    channel_match = direct_match(name, "La Liga BAR 1080", "LaLiga TV Bar")
    if not channel_match.channel:
        channel_match = direct_match(name, "Laliga TV BAR FHD", "LaLiga TV Bar")
    return channel_match


def match_movistar_plus(name):
    match = re.search(r"M(?:OVISTAR|\+) PLUS(?: (\d+))?(?: (FHD))?", name, re.IGNORECASE)
    if not match:
        return ChannelMatch()
    number = match.group(1)
    try:
        return ChannelMatch(
            Channel.objects.get(name__startswith=(f"Movistar Plus+ {number} (" if number else "Movistar Plus+ (")),
            get_quality(name),
            get_category(name),
        )
    except Channel.DoesNotExist:
        return ChannelMatch()


def match_motogp(name):
    return direct_match(name, "MGPTV | Camara de a bordo", "MotoGP Videopass")


def match_catchall(name):
    for channel_match in [
        direct_match(name, "TELECINCO FHD", "Telecinco"),
        direct_match(name, "LA 1 FHD", "La 1 TVE"),
        direct_match(name, "LA 2 FHD", "La 2 TVE"),
        direct_match(name, "NBA TV", "NBA League Pass"),
        direct_match(name, "NBA NETWORK", "NBA League Pass"),
        direct_match(name, "GOL PLAY", "GOL PLAY (Síguelo en directo)"),
        direct_match(name, "Gol Play FHD", "GOL PLAY (Síguelo en directo)"),
        direct_match(name, "GOL PLAY", "GolTV Play"),
        direct_match(name, "Gol Play FHD", "GolTV Play"),
        direct_match(name, "Teledeporte FHD", "Teledeporte"),
    ]:
        if channel_match.channel:
            return channel_match
    return ChannelMatch()


CHANNEL_MATCHERS = [
    match_movistar_deportes,
    match_dazn,
    match_dazn_bar,
    match_vamos,
    match_vamos_ellas,
    match_eurosport,
    match_dazn_f1,
    match_copa_del_rey,
    match_m_laliga,
    match_dazn_laliga,
    match_hypermotion,
    match_liga_campeones,
    match_laliga_tv_bar,
    match_movistar_plus,
    match_gol_play,
    match_motogp,
    match_catchall,
]
