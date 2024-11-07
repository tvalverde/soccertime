"""
Example event source for testing the scraping architecture.

This source generates fictional events and can be used to verify
that the multi-source system works correctly without making
real HTTP requests.
"""

from datetime import datetime, timedelta
from typing import Iterator
import logging

from .base import (
    Event,
    EventDetails,
    EventSource,
    MatchDetails,
    RaceDetails,
    register_source,
)

logger = logging.getLogger(__name__)


# Sample data for generating test events
SAMPLE_MATCHES = [
    {
        "sport": "Fútbol",
        "competition": "Liga de Prueba",
        "local": "Equipo Alpha",
        "visitor": "Equipo Beta",
    },
    {
        "sport": "Fútbol",
        "competition": "Liga de Prueba",
        "local": "Equipo Gamma",
        "visitor": "Equipo Delta",
    },
    {
        "sport": "Baloncesto",
        "competition": "Copa Ejemplo",
        "local": "Basket Team A",
        "visitor": "Basket Team B",
    },
]

SAMPLE_RACES = [
    {
        "sport": "Automovilismo",
        "competition": "GP de Prueba",
        "name": "Carrera Principal",
        "details": "Circuito de Ejemplo - 50 vueltas",
    },
    {
        "sport": "Ciclismo",
        "competition": "Vuelta de Prueba",
        "name": "Etapa 1",
        "details": "Montaña - 180km",
    },
]

SAMPLE_EVENTS = [
    {
        "sport": "Tenis",
        "competition": "Open de Ejemplo",
        "name": "Final Individual Masculino",
        "details": "Pista Central",
    },
    {
        "sport": "Golf",
        "competition": "Masters de Prueba",
        "name": "Ronda Final",
        "details": "Campo de Ejemplo",
    },
]

SAMPLE_CHANNELS = ["Canal Test 1", "Canal Test 2", "Deportes HD"]


@register_source
class ExampleSource(EventSource):
    """
    Example event source that generates fictional test events.
    
    Useful for testing the scraping architecture without
    making real network requests.
    
    This source is disabled by default to prevent accidental
    insertion of test data into production databases.
    """
    
    @property
    def name(self) -> str:
        return "example"
    
    @property
    def description(self) -> str:
        return "Fuente de ejemplo con eventos ficticios para pruebas"
    
    @property
    def enabled(self) -> bool:
        return False
    
    def get_events(self) -> Iterator[Event]:
        """Generate sample events for testing."""
        logger.info("[Example] Generating test events...")
        
        base_date = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
        event_count = 0
        
        # Generate match events
        for i, match_data in enumerate(SAMPLE_MATCHES):
            event_datetime = base_date + timedelta(days=i, hours=i % 3)
            
            event = Event(
                datetime=event_datetime,
                sport=match_data["sport"],
                competition=match_data["competition"],
                competition_crest=None,
                channels=SAMPLE_CHANNELS[:2],
                details=MatchDetails(
                    local=match_data["local"],
                    local_crest=None,
                    visitor=match_data["visitor"],
                    visitor_crest=None,
                    details=f"Jornada {i + 1}",
                ),
            )
            event_count += 1
            yield event
        
        # Generate race events
        for i, race_data in enumerate(SAMPLE_RACES):
            event_datetime = base_date + timedelta(days=i + 3, hours=14)
            
            event = Event(
                datetime=event_datetime,
                sport=race_data["sport"],
                competition=race_data["competition"],
                competition_crest=None,
                channels=SAMPLE_CHANNELS,
                details=RaceDetails(
                    name=race_data["name"],
                    details=race_data["details"],
                ),
            )
            event_count += 1
            yield event
        
        # Generate simple events
        for i, event_data in enumerate(SAMPLE_EVENTS):
            event_datetime = base_date + timedelta(days=i + 5, hours=16)
            
            event = Event(
                datetime=event_datetime,
                sport=event_data["sport"],
                competition=event_data["competition"],
                competition_crest=None,
                channels=[SAMPLE_CHANNELS[0]],
                details=EventDetails(
                    name=event_data["name"],
                    details=event_data["details"],
                ),
            )
            event_count += 1
            yield event
        
        logger.info(f"[Example] Generated {event_count} test events")
