import datetime
import io

import requests
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


class Command(BaseCommand):
    help = "Scrape sporting events from configured sources"

    def add_arguments(self, parser):
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

    def handle(self, *args, **options):
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
            source_class = get_source(source_name)
            if source_class is None:
                raise CommandError(f"Unknown source '{source_name}'. Available sources: {list_source_names()}")
            source = source_class()
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

    def process_source(self, source: EventSource):
        """Process events from a single source."""
        event_count = 0
        for agenda_event in source.get_events():
            self.process_event(agenda_event)
            event_count += 1
        if self.dry_run:
            self.stdout.write(f"  Total events: {event_count}")

    def display_event(self, event: Event):
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

    def process_event(self, agenda_event: Event):
        """Process a single event."""
        # In dry-run mode, just display the event
        if self.dry_run:
            self.display_event(agenda_event)
            return

        sport, _ = Sport.objects.get_or_create(name=agenda_event.sport)

        flag = self.get_or_create_flag(agenda_event.competition_crest)

        competition, _ = Competition.objects.get_or_create(
            name=agenda_event.competition, sport=sport, defaults={"flag": flag}
        )

        if not competition.flag and flag:
            competition.flag = flag
            competition.save()

        event_datetime = timezone.make_aware(agenda_event.datetime, timezone=timezone.get_current_timezone())

        if isinstance(agenda_event.details, MatchDetails):
            event = self.save_match_event(competition, event_datetime, agenda_event)
        elif isinstance(agenda_event.details, RaceDetails):
            event = self.save_race_event(competition, event_datetime, agenda_event)
        elif isinstance(agenda_event.details, EventDetails):
            event = self.save_simple_event(competition, event_datetime, agenda_event)
        else:
            self.stderr.write(f"Unhandled event type: {agenda_event}")
            return

        if not event:
            return

        self.update_channels(event, agenda_event.channels)

    def get_or_create_flag(self, flag_url):
        """Get or create a flag from URL."""
        if not flag_url:
            return None

        flag, _ = Flag.objects.get_or_create(name=flag_url, defaults={"display_name": flag_url})

        if not flag.image or not flag.image.storage.exists(flag.image.name):
            response = requests.get(flag_url, stream=True, timeout=10)
            if response.status_code == 200:
                flag.save_flag(io.BytesIO(response.content), flag_url)

        return flag

    def update_channels(self, event, channels):
        event.channels.clear()
        for channel_name in channels:
            channel, _ = Channel.objects.get_or_create(name=channel_name)
            event.channels.add(channel)

    def save_simple_event(self, competition, event_datetime, event):
        try:
            simple_event = SimpleEvent.objects.get(
                competition=competition,
                name=event.details.name,
                details=event.details.details,
                date__range=(event_datetime - datetime.timedelta(days=2), event_datetime + datetime.timedelta(days=2)),
            )
            if simple_event.date != event_datetime:
                simple_event.date = event_datetime
                simple_event.save()
        except SimpleEvent.DoesNotExist:
            simple_event, _ = SimpleEvent.objects.get_or_create(
                competition=competition,
                name=event.details.name,
                details=event.details.details,
                date=event_datetime,
            )
        except SimpleEvent.MultipleObjectsReturned:
            simple_events = SimpleEvent.objects.filter(
                competition=competition,
                name=event.details.name,
                details=event.details.details,
                date__range=(event_datetime - datetime.timedelta(days=2), event_datetime + datetime.timedelta(days=2)),
            )
            simple_event = simple_events.order_by("-last_updated_at").first()
            simple_events.exclude(id=simple_event.id).delete()
            if simple_event.date != event_datetime:
                simple_event.date = event_datetime
                simple_event.save()

        return simple_event

    def save_race_event(self, competition, event_datetime, event):
        try:
            race = Race.objects.get(
                competition=competition,
                name=event.details.name,
                details=event.details.details,
                date__range=(event_datetime - datetime.timedelta(days=2), event_datetime + datetime.timedelta(days=2)),
            )
            if race.date != event_datetime:
                race.date = event_datetime
                race.save()
        except Race.DoesNotExist:
            race, _ = Race.objects.get_or_create(
                competition=competition,
                name=event.details.name,
                details=event.details.details,
                date=event_datetime,
            )
        except Race.MultipleObjectsReturned:
            races = Race.objects.filter(
                competition=competition,
                name=event.details.name,
                details=event.details.details,
                date__range=(event_datetime - datetime.timedelta(days=2), event_datetime + datetime.timedelta(days=2)),
            )
            race = races.order_by("-last_updated_at").first()
            races.exclude(id=race.id).delete()
            if race.date != event_datetime:
                race.date = event_datetime
                race.save()

        return race

    def save_match_event(self, competition, event_datetime, event):
        local, _ = Team.objects.get_or_create(name=event.details.local)
        if not local.crest or not local.crest.storage.exists(local.crest.name):
            response = requests.get(event.details.local_crest, stream=True, timeout=10)
            if response.status_code == 200:
                local.save_crest(io.BytesIO(response.content), event.details.local_crest)
        visitor, _ = Team.objects.get_or_create(name=event.details.visitor)

        if not visitor.crest or not visitor.crest.storage.exists(visitor.crest.name):
            response = requests.get(event.details.visitor_crest, stream=True, timeout=10)
            if response.status_code == 200:
                visitor.save_crest(io.BytesIO(response.content), event.details.visitor_crest)

        try:
            match = Match.objects.get(
                competition=competition,
                local=local,
                visitor=visitor,
                date__range=(event_datetime - datetime.timedelta(days=2), event_datetime + datetime.timedelta(days=2)),
            )
            if match.date != event_datetime:
                match.date = event_datetime
                match.save()
        except Match.DoesNotExist:
            match, created = Match.objects.get_or_create(
                competition=competition,
                local=local,
                visitor=visitor,
                date=event_datetime,
                defaults={"details": event.details.details},
            )
            if not created:
                match.details = event.details.details
                match.save()
        except Match.MultipleObjectsReturned:
            matches = Match.objects.filter(
                competition=competition,
                local=local,
                visitor=visitor,
                date__range=(event_datetime - datetime.timedelta(days=2), event_datetime + datetime.timedelta(days=2)),
            )
            match = matches.order_by("-last_updated_at").first()
            matches.exclude(id=match.id).delete()

        return match
