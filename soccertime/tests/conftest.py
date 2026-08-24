"""
Pytest fixtures for soccertime tests.

Fixtures are organized by model/concept and build on each other:
- Base fixtures: sport, flag, competition, team, channel, channel_link
- Event fixtures: match, race, simple_event
- Composite fixtures: favorite, event_with_channels
"""

import datetime

import pytest
from django.utils import timezone

from soccertime.models import (
    Channel,
    ChannelLink,
    ChannelLinkSource,
    Competition,
    Favorite,
    Flag,
    Match,
    Race,
    SimpleEvent,
    Sport,
    Team,
)

# =============================================================================
# Base fixtures
# =============================================================================


@pytest.fixture
def sport(db):
    """Create a basic sport (Fútbol)."""
    return Sport.objects.create(name="Fútbol", order=1)


@pytest.fixture
def sport_cycling(db):
    """Create a cycling sport."""
    return Sport.objects.create(name="Ciclismo", order=2)


@pytest.fixture
def sport_tennis(db):
    """Create a tennis sport."""
    return Sport.objects.create(name="Tenis", order=3)


@pytest.fixture
def sports(sport, sport_cycling, sport_tennis):
    """Return all sports as a list."""
    return [sport, sport_cycling, sport_tennis]


@pytest.fixture
def flag(db):
    """Create a flag (Spain)."""
    return Flag.objects.create(
        name="spain",
        display_name="España",
    )


@pytest.fixture
def flag_france(db):
    """Create a French flag."""
    return Flag.objects.create(
        name="france",
        display_name="Francia",
    )


@pytest.fixture
def competition(db, sport, flag):
    """Create a basic competition (La Liga)."""
    return Competition.objects.create(
        name="La Liga",
        sport=sport,
        flag=flag,
    )


@pytest.fixture
def competition_champions(db, sport):
    """Create Champions League competition."""
    return Competition.objects.create(
        name="UEFA Champions League",
        sport=sport,
    )


@pytest.fixture
def competition_tour(db, sport_cycling, flag_france):
    """Create Tour de France competition."""
    return Competition.objects.create(
        name="Tour de Francia",
        sport=sport_cycling,
        flag=flag_france,
    )


@pytest.fixture
def competition_roland_garros(db, sport_tennis, flag_france):
    """Create Roland Garros competition."""
    return Competition.objects.create(
        name="Roland Garros",
        sport=sport_tennis,
        flag=flag_france,
    )


@pytest.fixture
def team_home(db):
    """Create a home team (Real Madrid)."""
    return Team.objects.create(name="Real Madrid")


@pytest.fixture
def team_away(db):
    """Create an away team (Barcelona)."""
    return Team.objects.create(name="FC Barcelona")


@pytest.fixture
def team_third(db):
    """Create a third team (Atlético Madrid)."""
    return Team.objects.create(name="Atlético de Madrid")


@pytest.fixture
def teams(team_home, team_away, team_third):
    """Return all teams as a list."""
    return [team_home, team_away, team_third]


@pytest.fixture
def channel(db):
    """Create a basic channel (Movistar LaLiga)."""
    return Channel.objects.create(name="Movistar LaLiga")


@pytest.fixture
def channel_dazn(db):
    """Create DAZN channel."""
    return Channel.objects.create(name="DAZN")


@pytest.fixture
def channels(channel, channel_dazn):
    """Return all channels as a list."""
    return [channel, channel_dazn]


@pytest.fixture
def channel_link_source(db):
    return ChannelLinkSource.objects.create(name="test")


@pytest.fixture
def channel_link(db, channel_link_source):
    """Create a basic channel link."""
    link = ChannelLink.objects.create(
        name="Movistar LaLiga HD",
        category="Deportes",
        subcategory="Fútbol",
        quality=ChannelLink.Quality.HD,
        link="https://example.com/stream1",
        enabled=True,
    )
    link.sources.add(channel_link_source)
    return link


@pytest.fixture
def channel_link_disabled(db, channel_link_source):
    """Create a disabled channel link."""
    link = ChannelLink.objects.create(
        name="Movistar LaLiga SD",
        category="Deportes",
        subcategory="Fútbol",
        quality=ChannelLink.Quality.SD,
        link="https://example.com/stream2",
        enabled=False,
    )
    link.sources.add(channel_link_source)
    return link


@pytest.fixture
def channel_with_links(channel, channel_link, channel_link_disabled):
    """Create a channel with associated links (enabled and disabled)."""
    channel.links.add(channel_link, channel_link_disabled)
    return channel


# =============================================================================
# Event fixtures
# =============================================================================


@pytest.fixture
def match(db, competition, team_home, team_away):
    """Create a basic match for today."""
    return Match.objects.create(
        competition=competition,
        local=team_home,
        visitor=team_away,
        date=timezone.now() + datetime.timedelta(hours=2),
    )


@pytest.fixture
def match_past(db, competition, team_home, team_away):
    """Create a match in the past (yesterday)."""
    return Match.objects.create(
        competition=competition,
        local=team_away,  # Reversed teams for uniqueness
        visitor=team_home,
        date=timezone.now() - datetime.timedelta(days=1),
    )


@pytest.fixture
def match_future(db, competition_champions, team_home, team_third):
    """Create a match in the future (next week)."""
    return Match.objects.create(
        competition=competition_champions,
        local=team_home,
        visitor=team_third,
        date=timezone.now() + datetime.timedelta(days=7),
    )


@pytest.fixture
def match_in_progress(db, competition, team_third, team_away):
    """Create a match that started 1 hour ago (in progress)."""
    return Match.objects.create(
        competition=competition,
        local=team_third,
        visitor=team_away,
        date=timezone.now() - datetime.timedelta(hours=1),
    )


@pytest.fixture
def race(db, competition_tour):
    """Create a basic race event."""
    return Race.objects.create(
        competition=competition_tour,
        name="Etapa 15 - Montaña",
        date=timezone.now() + datetime.timedelta(hours=3),
        details="Etapa de alta montaña con 3 puertos",
    )


@pytest.fixture
def race_past(db, competition_tour):
    """Create a past race event."""
    return Race.objects.create(
        competition=competition_tour,
        name="Etapa 14 - Llana",
        date=timezone.now() - datetime.timedelta(days=1),
    )


@pytest.fixture
def simple_event(db, competition_roland_garros):
    """Create a basic simple event."""
    return SimpleEvent.objects.create(
        competition=competition_roland_garros,
        name="Final Masculina",
        date=timezone.now() + datetime.timedelta(hours=4),
        details="Nadal vs Djokovic",
    )


@pytest.fixture
def simple_event_past(db, competition_roland_garros):
    """Create a past simple event."""
    return SimpleEvent.objects.create(
        competition=competition_roland_garros,
        name="Semifinal Femenina",
        date=timezone.now() - datetime.timedelta(days=2),
    )


@pytest.fixture
def match_with_channels(match, channel, channel_dazn):
    """Create a match with associated channels."""
    match.channels.add(channel, channel_dazn)
    return match


# =============================================================================
# Favorite fixtures
# =============================================================================


@pytest.fixture
def favorite_competition(db, competition):
    """Create a favorite competition."""
    return Favorite.objects.create(
        competition=competition,
        order=1,
    )


@pytest.fixture
def favorite_team(db, team_home, competition):
    """Create a favorite team."""
    return Favorite.objects.create(
        competition=competition,
        team=team_home,
        order=2,
    )


@pytest.fixture
def favorites(favorite_competition, favorite_team):
    """Return all favorites as a list."""
    return [favorite_competition, favorite_team]


# =============================================================================
# Utility fixtures
# =============================================================================


@pytest.fixture
def all_events(match, match_past, match_future, match_in_progress, race, race_past, simple_event, simple_event_past):
    """Create a variety of events for comprehensive testing."""
    return {
        "match": match,
        "match_past": match_past,
        "match_future": match_future,
        "match_in_progress": match_in_progress,
        "race": race,
        "race_past": race_past,
        "simple_event": simple_event,
        "simple_event_past": simple_event_past,
    }


@pytest.fixture
def future_events(match, match_future, race, simple_event):
    """Only future events."""
    return [match, match_future, race, simple_event]


@pytest.fixture
def past_events(match_past, race_past, simple_event_past):
    """Only past events."""
    return [match_past, race_past, simple_event_past]


# =============================================================================
# Image download
# =============================================================================
#
# `download_image` resolves the hostname to refuse addresses inside the deployment, so a
# test that does not stub the lookup makes a real DNS query — slow, and dependent on the
# machine having a network. Anything exercising the download path takes `public_dns`.


@pytest.fixture
def public_dns(monkeypatch):
    """Resolve every hostname to a public address, so only the response is under test."""
    monkeypatch.setattr(
        "soccertime.management.commands._image_download.socket.getaddrinfo",
        lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )


def image_response(body, status=200, content_type="image/png", headers=None, is_redirect=False):
    """A stand-in for `requests.Response` carrying only what the downloader reads.

    Faithful about `is_redirect` in particular: a bare `Mock` answers truthily to it, so a
    test built on one has every response treated as a redirect.
    """
    from unittest.mock import Mock

    import requests

    response = Mock(spec=requests.Response)
    response.status_code = status
    response.is_redirect = is_redirect
    response.headers = {"Content-Type": content_type, **(headers or {})}
    response.iter_content = Mock(side_effect=lambda size: iter([body[i : i + size] for i in range(0, len(body), size)]))
    response.close = Mock()
    return response


# =============================================================================
# Remote playlist fetching
# =============================================================================


def remote_text_response(body, status=200, content_type="text/plain"):
    """A real `requests.Response` carrying `body`, for the `--url` import path.

    Real rather than a `Mock` on purpose: what these tests guard is how the body is
    decoded, and `requests` only applies its ISO-8859-1 fallback for a charset-less
    text/* response inside the genuine class. A mock would answer whatever was set on it
    and the regression could not fail.
    """
    from io import BytesIO

    import requests
    from requests.utils import get_encoding_from_headers

    response = requests.Response()
    response.status_code = status
    response.raw = BytesIO(body)
    response.headers["Content-Type"] = content_type
    # What `Session.send` does, and the whole point of the exercise: a charset-less
    # text/* response is stamped ISO-8859-1 here, so `response.text` would lie.
    response.encoding = get_encoding_from_headers(response.headers)
    return response
