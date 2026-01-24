"""
Base module for event scraping sources.

This module defines the common data structures and abstract base class
that all event sources must implement.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EventDetails:
    """Details for a simple/generic event."""

    name: str | None = None
    details: str | None = None


@dataclass
class RaceDetails:
    """Details for a race event (motorsports, cycling, etc.)."""

    name: str | None = None
    details: str | None = None


@dataclass
class MatchDetails:
    """Details for a match event (two teams competing)."""

    local: str | None = None
    local_crest: str | None = None
    visitor: str | None = None
    visitor_crest: str | None = None
    details: str | None = None


@dataclass
class Event:
    """Represents a sporting event from any source."""

    datetime: datetime | None = None
    details: EventDetails = field(default_factory=EventDetails)
    sport: str | None = None
    competition: str | None = None
    competition_crest: str | None = None
    channels: list[str] | None = None

    def __post_init__(self):
        if self.channels is None:
            self.channels = []


class EventSource(ABC):
    """
    Abstract base class for event sources.

    All event sources must implement this interface to be compatible
    with the scraping command.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique identifier for this source."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a human-readable description of this source."""
        pass

    @property
    def enabled(self) -> bool:
        """
        Return whether this source is enabled.

        Disabled sources are skipped by default but can be run
        explicitly with --include-disabled flag.
        Override this property to disable a source.
        """
        return True

    @abstractmethod
    def get_events(self) -> Iterator[Event]:
        """
        Fetch and yield events from this source.

        Yields:
            Event: Parsed event objects
        """
        pass


# Registry of available event sources
_sources: dict[str, type[EventSource]] = {}


def register_source(source_class: type[EventSource]) -> type[EventSource]:
    """
    Decorator to register an event source.

    Usage:
        @register_source
        class MySource(EventSource):
            ...
    """
    # Create a temporary instance to get the name
    # We need to handle this carefully for abstract classes
    source_name = source_class.__name__.lower().replace("source", "")
    _sources[source_name] = source_class
    return source_class


def get_source(name: str) -> type[EventSource] | None:
    """Get a registered source by name."""
    return _sources.get(name)


def get_available_sources(include_disabled: bool = False) -> dict[str, type[EventSource]]:
    """Get all registered sources, optionally including disabled ones."""
    if include_disabled:
        return _sources.copy()
    return {name: src for name, src in _sources.items() if src().enabled}


def list_source_names() -> list[str]:
    """Get list of registered source names."""
    return list(_sources.keys())
