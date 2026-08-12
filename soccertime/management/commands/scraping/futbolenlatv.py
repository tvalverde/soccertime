import logging
import os
from collections.abc import Iterator
from datetime import date as date_type
from datetime import datetime, timedelta
from datetime import time as time_type
from typing import Any
from urllib.parse import urljoin

import requests
import requests_cache
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import (
    Event,
    EventDetails,
    EventSource,
    MatchDetails,
    RaceDetails,
    ScrapeUnit,
    register_source,
)

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants
DATE_FORMAT = "%d/%m/%Y"
TIME_FORMAT = "%H:%M"
REQUEST_TIMEOUT = 30
RACE_SPORTS = {"Automovilismo", "Motociclismo"}
MAX_FUTURE_DAYS = 365

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


def _configure_cache() -> None:
    cache_path = os.environ.get("REQUESTS_CACHE", "soccertime_data_cache")
    cache_dir = os.path.dirname(cache_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    requests_cache.install_cache(cache_path, expire_after=timedelta(hours=6))


# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)


class ScrapingStats:
    """Track scraping statistics."""

    def __init__(self) -> None:
        self.processed = 0
        self.skipped = 0
        self.errors = 0
        self.pending_time = 0

    def add(self, other: "ScrapingStats") -> None:
        """Fold another page's counts into these."""
        self.processed += other.processed
        self.skipped += other.skipped
        self.errors += other.errors
        self.pending_time += other.pending_time

    def __str__(self) -> str:
        return (
            f"processed={self.processed}, skipped={self.skipped}, "
            f"errors={self.errors}, pending_time={self.pending_time}"
        )


def clean_text(text: str) -> str:
    """Clean and normalize text by removing extra whitespace."""
    if text:
        return " ".join(text.split()).strip()
    return text


def extract_image_url(tag: Any, base_url: str) -> str | None:
    """Safely extract image URL from a tag."""
    if not tag:
        return None
    img = tag.find("img") if not (isinstance(tag, Tag) and tag.name == "img") else tag
    if not img or not isinstance(img, Tag):
        return None
    # An attribute can be multi-valued in HTML; src never is, but the parser cannot say so.
    src = img.get("src")
    if isinstance(src, str):
        return urljoin(base_url, src)
    return None


def is_valid_date(date: date_type | None, max_future_days: int = MAX_FUTURE_DAYS) -> bool:
    """Check if date is reasonable (not too far in the future)."""
    if not date:
        return False
    max_date = datetime.now().date() + timedelta(days=max_future_days)
    min_date = datetime.now().date() - timedelta(days=7)  # Allow recent past events
    return min_date <= date <= max_date


def parse_date_row(row: Any, sport: str, url: str) -> date_type | None:
    """Parse date from a header row."""
    date_text = row.get_text(strip=True)
    try:
        date = datetime.strptime(date_text.split(", ")[-1], DATE_FORMAT).date()
        if not is_valid_date(date):
            logger.warning(f"[{sport}] Date out of valid range: '{date}' from '{url}'")
            return None
        return date
    except (ValueError, IndexError) as e:
        logger.error(f"[{sport}] Error parsing date from text: '{date_text}' in {url}. Error: {e}")
        return None


def parse_competition_row(row: Any, base_url: str) -> tuple[str | None, str | None]:
    """Parse competition name and crest from a competition header row."""
    try:
        anchor = row.find("a")
        if anchor:
            competition = clean_text(" ".join(anchor.stripped_strings))
        else:
            competition = clean_text(" ".join(row.stripped_strings))
    except AttributeError:
        competition = clean_text(" ".join(row.stripped_strings))

    crest_img = row.find("img")
    competition_crest = extract_image_url(crest_img, base_url)

    return competition, competition_crest


def parse_time(time_text: str, sport: str, row_text: str, url: str) -> time_type | None:
    """Parse time from text."""
    try:
        return datetime.strptime(time_text, TIME_FORMAT).time()
    except ValueError:
        logger.error(f"[{sport}] Error parsing time '{time_text}' for event in {url}. Row: {row_text[:100]}...")
        return None


def parse_competition_from_col(
    col: Any, base_url: str, current_competition: str | None, current_crest: str | None
) -> tuple[str | None, str | None, str]:
    """Parse competition info from column 1 when it contains images/labels."""
    competition = current_competition
    competition_crest = current_crest
    details = ""

    if col.find("img"):
        label = col.find("label")
        if label:
            competition = clean_text(" ".join(label.stripped_strings))
            competition_crest = extract_image_url(col, base_url)
            details_span = col.find("span")
            if details_span:
                inner_span = details_span.find("span")
                if inner_span:
                    details_span = inner_span
                details = clean_text(" ".join(details_span.stripped_strings)) or ""
        else:
            span_in_col = col.find("span")
            if span_in_col:
                competition = clean_text(" ".join(span_in_col.stripped_strings))
    elif col.find("span"):
        details = clean_text(" ".join(col.find("span").stripped_strings)) or ""

    return competition, competition_crest, details


def parse_simple_event(cols: Any, sport: str, details: str) -> tuple[str, str | None, list[str]]:
    """Parse a simple event (4 columns - no teams)."""
    event_name = ""
    event_details = details

    try:
        strings = list(cols[2].stripped_strings)
        if len(strings) >= 2:
            event_name, event_details = strings[0], strings[1]
        elif len(strings) == 1:
            event_name = strings[0]
    except (ValueError, IndexError):
        event_name = clean_text(" ".join(cols[2].stripped_strings))

    event_name = clean_text(event_name)
    event_details = clean_text(event_details) if event_details else details

    channels = [clean_text(li.get_text(strip=True)) for li in cols[3].find_all("li")]

    return event_name, event_details, channels


def extract_team_slug(col: Any) -> str | None:
    """Extract the futbolenlatv team slug from an <a> link in a team column."""
    anchor = col.find("a", class_="internalLink")
    if anchor and anchor.get("href", "").startswith("/equipo/"):
        return anchor["href"].removeprefix("/equipo/")
    return None


def parse_match_event(
    cols: Any, base_url: str, details: str
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None, list[str]]:
    """Parse a match event (5+ columns - with teams)."""
    # Home team
    home_team_span = cols[2].find("span")
    home_team = clean_text(" ".join(home_team_span.stripped_strings)) if home_team_span else None
    home_crest = extract_image_url(cols[2], base_url)
    home_slug = extract_team_slug(cols[2])

    # Away team
    away_team_span = cols[3].find("span")
    away_team = clean_text(" ".join(away_team_span.stripped_strings)) if away_team_span else None
    away_crest = extract_image_url(cols[3], base_url)
    away_slug = extract_team_slug(cols[3])

    # Channels (safely access cols[4])
    channels = []
    if len(cols) > 4:
        channels = [clean_text(li.get_text(strip=True)) for li in cols[4].find_all("li")]

    return home_team, home_crest, home_slug, away_team, away_crest, away_slug, channels


def parse_iter(soup: Any, sport: str, base_url: str, stats: ScrapingStats | None = None) -> Iterator[Event]:
    """Parse events from soup for a given sport."""
    if stats is None:
        stats = ScrapingStats()

    tables = soup.find_all(lambda tag: tag.name == "table" and tag.find_all("tr", attrs={"class": "cabeceraTabla"}))

    for table in tables:
        date = None
        competition = None
        competition_crest = None

        if not isinstance(table, Tag):
            continue

        for row in table.find_all("tr"):
            if not isinstance(row, Tag):
                continue

            # get_attribute_list always returns a list, unlike get() on a multi-valued attribute
            row_classes = row.get_attribute_list("class")

            # Date header row
            if "cabeceraTabla" in row_classes:
                date = parse_date_row(row, sport, base_url)
                continue

            # Competition header row
            if "cabeceraCompericion" in row_classes:
                competition, competition_crest = parse_competition_row(row, base_url)
                continue

            # Event row
            cols = row.find_all("td")
            if len(cols) < 4:
                continue

            # Parse time
            time_text = cols[0].get_text(strip=True)
            if time_text == "PD":
                # "Por Determinar": the event is real and dated, only its broadcast time
                # has not been announced. Counted apart from the malformed rows in
                # `skipped`, and logged, because it used to vanish without a trace: these
                # are the only discarded rows that raise no warning, which is how 42 of
                # them went unnoticed for months. They are still not stored — an agenda
                # entry with no time has nowhere to sit in a listing ordered by time.
                stats.pending_time += 1
                description = clean_text(" ".join(cols[2].stripped_strings))[:60]
                logger.info(f"[{sport}] Time not announced yet, not stored: {description}")
                continue

            if date is None:
                logger.warning(
                    f"[{sport}] Skipping event row as date was not parsed in {base_url}. Row: {row.get_text(strip=True)[:100]}..."
                )
                stats.skipped += 1
                continue

            event_time = parse_time(time_text, sport, row.get_text(strip=True), base_url)
            if event_time is None:
                stats.errors += 1
                continue

            # Parse competition from column if present
            competition, competition_crest, details = parse_competition_from_col(
                cols[1], base_url, competition, competition_crest
            )

            if competition is None:
                logger.error(
                    f"[{sport}] Skipping event row as competition was not parsed in {base_url}. Row: {row.get_text(strip=True)[:100]}..."
                )
                stats.errors += 1
                continue

            # Parse event based on column count
            if len(cols) == 4:
                # Simple event or race
                event_name, event_details, channels = parse_simple_event(cols, sport, details)

                if not event_name:
                    logger.warning(f"[{sport}] Skipping event with empty name in {base_url}")
                    stats.skipped += 1
                    continue

                event_details_obj: RaceDetails | EventDetails
                if sport in RACE_SPORTS:
                    event_details_obj = RaceDetails(name=event_name, details=event_details)
                else:
                    event_details_obj = EventDetails(name=event_name, details=event_details)

                event = Event(
                    datetime=datetime.combine(date, event_time),
                    sport=sport,
                    competition=competition,
                    competition_crest=competition_crest,
                    channels=channels,
                    details=event_details_obj,
                )
            else:
                # Match event
                home_team, home_crest, home_slug, away_team, away_crest, away_slug, channels = parse_match_event(
                    cols, base_url, details
                )

                if not home_team or not away_team:
                    logger.warning(
                        f"[{sport}] Skipping match with missing team names. Home: '{home_team}', Away: '{away_team}' in {base_url}"
                    )
                    stats.skipped += 1
                    continue

                event = Event(
                    datetime=datetime.combine(date, event_time),
                    sport=sport,
                    competition=competition,
                    competition_crest=competition_crest,
                    channels=channels,
                    details=MatchDetails(
                        local=home_team,
                        local_crest=home_crest,
                        local_slug=home_slug,
                        visitor=away_team,
                        visitor_crest=away_crest,
                        visitor_slug=away_slug,
                        details=details,
                    ),
                )

            stats.processed += 1
            yield event


EVENTS_PAGES = [
    {"sport": "Fútbol", "url": "https://www.futbolenlatv.es/"},
    {"sport": "Baloncesto", "url": "https://www.futbolenlatv.es/deporte/baloncesto"},
    {"sport": "Tenis", "url": "https://www.futbolenlatv.es/deporte/tenis"},
    {"sport": "Automovilismo", "url": "https://www.futbolenlatv.es/deporte/automovilismo"},
    {"sport": "Motociclismo", "url": "https://www.futbolenlatv.es/deporte/motociclismo"},
    {"sport": "Ciclismo", "url": "https://www.futbolenlatv.es/deporte/ciclismo"},
    {"sport": "Golf", "url": "https://www.futbolenlatv.es/deporte/golf"},
]


def create_session() -> requests.Session:
    """Create a requests session with retry strategy."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


TEAM_PAGE_BASE_URL = "https://www.futbolenlatv.es/equipo/"
TEAM_PAGE_SPORT = "Fútbol"


def get_favorite_team_slugs() -> list[str]:
    from soccertime.models import Team

    slugs = (
        Team.objects.filter(
            favorite__isnull=False,
            futbolenlatv_slug__isnull=False,
        )
        .exclude(futbolenlatv_slug="")
        .values_list("futbolenlatv_slug", flat=True)
        .distinct()
    )
    return [slug for slug in slugs if slug]


def iter_units() -> Iterator[ScrapeUnit]:
    """Each page as a unit with its declared scope, which is what reconciliation runs on.

    A sport agenda page covers that sport for the days it showed; a team page covers that
    team's fixtures. A page that raises mid-parse still hands over what it yielded, but
    marked incomplete: a partial view stores events and judges nothing.
    """
    _configure_cache()
    session = create_session()
    total_stats = ScrapingStats()

    for info in EVENTS_PAGES:
        url = info["url"]
        sport = info["sport"]
        page_stats = ScrapingStats()
        events: list[Event] = []
        complete = True
        try:
            response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")
            events = list(parse_iter(soup, sport, url, page_stats))
            total_stats.add(page_stats)
            logger.info(f"[{sport}] Completed: {page_stats}")
        except requests.exceptions.Timeout:
            logger.error(f"[{sport}] Timeout fetching URL {url} after {REQUEST_TIMEOUT}s")
            total_stats.errors += 1
            complete = False
        except requests.exceptions.RequestException as e:
            logger.error(f"[{sport}] Network/HTTP error fetching {url}: {type(e).__name__}: {e}")
            total_stats.errors += 1
            complete = False
        except Exception as e:
            logger.critical(f"[{sport}] Unexpected error for {url}: {type(e).__name__}: {e}")
            total_stats.errors += 1
            complete = False
        yield ScrapeUnit(events=events, sport=sport, complete=complete, label=sport)

    for slug in get_favorite_team_slugs():
        url = f"{TEAM_PAGE_BASE_URL}{slug}"
        page_stats = ScrapingStats()
        events = []
        complete = True
        try:
            response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")
            events = list(parse_iter(soup, TEAM_PAGE_SPORT, url, page_stats))
            total_stats.add(page_stats)
            logger.info(f"[Team: {slug}] Completed: {page_stats}")
        except requests.exceptions.Timeout:
            logger.error(f"[Team: {slug}] Timeout fetching URL {url} after {REQUEST_TIMEOUT}s")
            total_stats.errors += 1
            complete = False
        except requests.exceptions.RequestException as e:
            logger.error(f"[Team: {slug}] Network/HTTP error fetching {url}: {type(e).__name__}: {e}")
            total_stats.errors += 1
            complete = False
        except Exception as e:
            logger.critical(f"[Team: {slug}] Unexpected error for {url}: {type(e).__name__}: {e}")
            total_stats.errors += 1
            complete = False
        yield ScrapeUnit(events=events, team_slug=slug, complete=complete, label=f"Team: {slug}")

    logger.info(f"Scraping complete. Total: {total_stats}")


def get_events() -> Iterator[Event]:
    """Fetch and parse events from all configured pages."""
    _configure_cache()
    session = create_session()
    total_stats = ScrapingStats()

    for info in EVENTS_PAGES:
        url = info["url"]
        sport = info["sport"]
        page_stats = ScrapingStats()

        try:
            response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "lxml")

            yield from parse_iter(soup, sport, url, page_stats)

            total_stats.add(page_stats)

            logger.info(f"[{sport}] Completed: {page_stats}")

        except requests.exceptions.Timeout:
            logger.error(f"[{sport}] Timeout fetching URL {url} after {REQUEST_TIMEOUT}s")
            total_stats.errors += 1
            continue
        except requests.exceptions.RequestException as e:
            logger.error(f"[{sport}] Network/HTTP error fetching {url}: {type(e).__name__}: {e}")
            total_stats.errors += 1
            continue
        except Exception as e:
            logger.critical(f"[{sport}] Unexpected error for {url}: {type(e).__name__}: {e}")
            total_stats.errors += 1
            continue

    # Scrape team pages for favorite teams with a futbolenlatv slug
    team_slugs = get_favorite_team_slugs()
    for slug in team_slugs:
        url = f"{TEAM_PAGE_BASE_URL}{slug}"
        page_stats = ScrapingStats()

        try:
            response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "lxml")
            yield from parse_iter(soup, TEAM_PAGE_SPORT, url, page_stats)

            total_stats.add(page_stats)

            logger.info(f"[Team: {slug}] Completed: {page_stats}")

        except requests.exceptions.Timeout:
            logger.error(f"[Team: {slug}] Timeout fetching URL {url} after {REQUEST_TIMEOUT}s")
            total_stats.errors += 1
            continue
        except requests.exceptions.RequestException as e:
            logger.error(f"[Team: {slug}] Network/HTTP error fetching {url}: {type(e).__name__}: {e}")
            total_stats.errors += 1
            continue
        except Exception as e:
            logger.critical(f"[Team: {slug}] Unexpected error for {url}: {type(e).__name__}: {e}")
            total_stats.errors += 1
            continue

    logger.info(f"Scraping complete. Total: {total_stats}")


@register_source
class FutbolEnLaTVSource(EventSource):
    """
    Event source for futbolenlatv.es website.

    Scrapes sporting events from multiple sport categories
    including football, basketball, tennis, motorsports, etc.
    """

    @property
    def name(self) -> str:
        return "futbolenlatv"

    @property
    def description(self) -> str:
        return "Eventos deportivos de futbolenlatv.es"

    def get_events(self) -> Iterator[Event]:
        """Fetch and parse events from futbolenlatv.es."""
        return get_events()

    def iter_units(self) -> Iterator[ScrapeUnit]:
        """Pages with their scopes, which is what lets reconciliation prune safely."""
        return iter_units()
