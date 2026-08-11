import datetime
from argparse import ArgumentParser
from typing import Any

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from soccertime.models import (
    Channel,
    Competition,
    Flag,
    Match,
    Race,
    SimpleEvent,
    Sport,
    Team,
)

from ._image_download import download_image

# Import sources to register them
from .scraping import (
    example,  # noqa: F401
    futbolenlatv,  # noqa: F401
)
from .scraping.base import (
    Event,
    EventDetails,
    EventSource,
    MatchDetails,
    RaceDetails,
    get_available_sources,
    get_source,
    list_source_names,
)

# Sources shift an announced event by hours or a day; within this window it is the same
# event rather than a new one.
DUPLICATE_WINDOW_DAYS = 2


class Command(BaseCommand):
    help = "Scrape sporting events from configured sources"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--source",
            type=str,
            default="all",
            help=f'Event source to use. Available: {list_source_names()} or "all" (default: all)',
        )
        parser.add_argument(
            "--list-sources",
            action="store_true",
            help="List all available event sources and exit",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show events without saving to database",
        )
        parser.add_argument(
            "--include-disabled",
            action="store_true",
            help="Include disabled sources when using --source=all or --list-sources",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        self.dry_run = options["dry_run"]
        include_disabled = options["include_disabled"]

        # Handle --list-sources
        if options["list_sources"]:
            self.stdout.write("Available event sources:")
            for name, source_class in get_available_sources(include_disabled=True).items():
                source = source_class()
                status = "" if source.enabled else " (disabled)"
                if not source.enabled and not include_disabled:
                    continue
                self.stdout.write(f"  - {name}: {source.description}{status}")
            return

        # Get sources to process
        source_name = options["source"]
        if source_name == "all":
            sources = [
                source_class() for source_class in get_available_sources(include_disabled=include_disabled).values()
            ]
        else:
            found = get_source(source_name)
            if found is None:
                raise CommandError(f"Unknown source '{source_name}'. Available sources: {list_source_names()}")
            source = found()
            # Allow running disabled sources explicitly by name
            if not source.enabled and not include_disabled:
                self.stdout.write(
                    self.style.WARNING(f"Source '{source_name}' is disabled. Use --include-disabled to run it anyway.")
                )
                return
            sources = [source]

        if not sources:
            raise CommandError("No event sources available.")

        if self.dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be saved to database"))
        else:
            self.init_caches()

        # Process all sources
        for source in sources:
            status = " (disabled)" if not source.enabled else ""
            self.stdout.write(f"Processing source: {source.name}{status}")
            self.process_source(source)

        if not self.dry_run:
            cache.clear()
            self.stdout.write(self.style.SUCCESS("Scraping completed successfully"))
        else:
            self.stdout.write(self.style.SUCCESS("Dry run completed"))

    def init_caches(self) -> None:
        """Initialize in-memory caches for reference objects to avoid DB hits in loops."""
        self._sports_cache = {s.name: s for s in Sport.objects.all()}
        self._flags_cache = {f.name: f for f in Flag.objects.all()}
        self._competitions_cache = {
            (c.name, c.sport_id): c for c in Competition.objects.select_related("sport", "flag")
        }
        self._teams_cache = {t.name: t for t in Team.objects.prefetch_related("favorite")}
        self._channels_cache = {c.name: c for c in Channel.objects.all()}

    def get_or_create_sport(self, name: str) -> Sport:
        if name in self._sports_cache:
            return self._sports_cache[name]
        sport, _ = Sport.objects.get_or_create(name=name)
        self._sports_cache[name] = sport
        return sport

    def get_or_create_competition(self, name: str, sport: Sport, flag: Flag | None) -> Competition:
        key = (name, sport.id)
        if key in self._competitions_cache:
            comp = self._competitions_cache[key]
            if not comp.flag and flag:
                comp.flag = flag
                comp.save(update_fields=["flag"])
            return comp
        comp, _ = Competition.objects.get_or_create(name=name, sport=sport, defaults={"flag": flag})
        self._competitions_cache[key] = comp
        return comp

    def get_or_create_team(self, name: str) -> Team:
        if name in self._teams_cache:
            return self._teams_cache[name]
        team, _ = Team.objects.get_or_create(name=name)
        self._teams_cache[name] = team
        return team

    def update_team_slug(self, team: Team, slug: str | None) -> None:
        """Update a team's futbolenlatv_slug if it's a favorite and the slug is new."""
        if not slug or team.futbolenlatv_slug:
            return
        if not getattr(team, "is_favorite_cached", False):
            return
        team.futbolenlatv_slug = slug
        team.save(update_fields=["futbolenlatv_slug"])
        self._teams_cache[team.name] = team
        self.stdout.write(self.style.SUCCESS(f"  Auto-discovered slug for '{team.name}': {slug}"))

    def get_or_create_channel(self, name: str) -> Channel:
        if name in self._channels_cache:
            return self._channels_cache[name]
        channel, _ = Channel.objects.get_or_create(name=name)
        self._channels_cache[name] = channel
        return channel

    def process_source(self, source: EventSource) -> None:
        """Process events from a single source."""
        event_count = 0
        for agenda_event in source.get_events():
            self.process_event(agenda_event)
            event_count += 1
        if self.dry_run:
            self.stdout.write(f"  Total events: {event_count}")

    def display_event(self, event: Event) -> None:
        """Display an event without saving it (for dry-run mode)."""
        details = event.details

        if isinstance(details, MatchDetails):
            event_desc = f"{details.local} vs {details.visitor}"
        elif isinstance(details, RaceDetails | EventDetails):
            event_desc = details.name
        else:
            event_desc = str(details)

        channels = ", ".join(event.channels) if event.channels else "N/A"

        self.stdout.write(
            f"  [{event.sport}] {event.competition} | "
            f"{event.datetime.strftime('%Y-%m-%d %H:%M')} | "
            f"{event_desc} | Channels: {channels}"
        )

    def process_event(self, agenda_event: Event) -> None:
        """Process a single event."""
        # In dry-run mode, just display the event
        if self.dry_run:
            self.display_event(agenda_event)
            return

        sport = self.get_or_create_sport(agenda_event.sport)
        flag = self.get_or_create_flag(agenda_event.competition_crest)
        competition = self.get_or_create_competition(agenda_event.competition, sport, flag)

        event_datetime = timezone.make_aware(agenda_event.datetime, timezone=timezone.get_current_timezone())

        event: Match | Race | SimpleEvent
        if isinstance(agenda_event.details, MatchDetails):
            event = self.save_match_event(competition, event_datetime, agenda_event.details)
        elif isinstance(agenda_event.details, RaceDetails):
            event = self.save_race_event(competition, event_datetime, agenda_event.details)
        elif isinstance(agenda_event.details, EventDetails):
            event = self.save_simple_event(competition, event_datetime, agenda_event.details)
        else:
            self.stderr.write(f"Unhandled event type: {agenda_event}")
            return

        if not event:
            return

        self.update_channels(event, agenda_event.channels)

    def get_or_create_flag(self, flag_url: str | None) -> Flag | None:
        """Get or create a flag from URL."""
        if not flag_url:
            return None

        if flag_url in self._flags_cache:
            flag = self._flags_cache[flag_url]
        else:
            flag, _ = Flag.objects.get_or_create(name=flag_url, defaults={"display_name": flag_url})
            self._flags_cache[flag_url] = flag

        if not flag.image or not flag.image.name or not flag.image.storage.exists(flag.image.name):
            image = download_image(flag_url, on_error=self.stderr.write)
            if image:
                flag.save_flag(image)

        return flag

    def ensure_crest(self, team: Team, crest_url: str | None) -> None:
        """Download the team crest when it is not stored yet."""
        if team.crest and team.crest.name and team.crest.storage.exists(team.crest.name):
            return
        image = download_image(crest_url, on_error=self.stderr.write)
        if image:
            team.save_crest(image)

    def update_channels(self, event: Match | Race | SimpleEvent, channels: list[str]) -> None:
        channel_objs = [self.get_or_create_channel(c) for c in channels]
        event.channels.set(channel_objs)

    def upsert_event(
        self,
        model: type[Any],
        lookup: dict[str, Any],
        event_datetime: datetime.datetime,
        defaults: dict[str, Any] | None = None,
    ) -> Any:
        """Find the event around this datetime and realign it, or create it.

        Sources shift a fixed event by a few hours or a day rather than announcing a new
        one, so a match within a two-day window counts as the same event. Where a shift
        has already produced duplicates, the most recently updated row wins and the rest
        are removed.
        """
        window = (
            event_datetime - datetime.timedelta(days=DUPLICATE_WINDOW_DAYS),
            event_datetime + datetime.timedelta(days=DUPLICATE_WINDOW_DAYS),
        )
        candidates = model.objects.filter(**lookup, date__range=window)
        event = candidates.order_by("-last_updated_at").first()

        if event is None:
            event, _ = model.objects.get_or_create(**lookup, date=event_datetime, defaults=defaults or {})
            return event

        candidates.exclude(pk=event.pk).delete()

        changed = []
        if event.date != event_datetime:
            event.date = event_datetime
            changed.append("date")
        for field, value in (defaults or {}).items():
            if getattr(event, field) != value:
                setattr(event, field, value)
                changed.append(field)
        if changed:
            event.save(update_fields=[*changed, "last_updated_at"])

        return event

    def save_simple_event(
        self, competition: Competition, event_datetime: datetime.datetime, details: EventDetails
    ) -> SimpleEvent:
        return self.upsert_event(
            SimpleEvent,
            {"competition": competition, "name": details.name, "details": details.details},
            event_datetime,
        )

    def save_race_event(
        self, competition: Competition, event_datetime: datetime.datetime, details: RaceDetails
    ) -> Race:
        return self.upsert_event(
            Race,
            {"competition": competition, "name": details.name, "details": details.details},
            event_datetime,
        )

    def save_match_event(
        self, competition: Competition, event_datetime: datetime.datetime, details: MatchDetails
    ) -> Match:
        local = self.get_or_create_team(details.local)
        visitor = self.get_or_create_team(details.visitor)

        self.ensure_crest(local, details.local_crest)
        self.ensure_crest(visitor, details.visitor_crest)

        self.update_team_slug(local, details.local_slug)
        self.update_team_slug(visitor, details.visitor_slug)

        return self.upsert_event(
            Match,
            {"competition": competition, "local": local, "visitor": visitor},
            event_datetime,
            defaults={"details": details.details},
        )
