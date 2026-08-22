import datetime
from argparse import ArgumentParser
from typing import Any
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
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
from soccertime.models import (
    Event as StoredEvent,
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
    ScrapeUnit,
    get_available_sources,
    get_source,
    list_source_names,
)

# Consecutive successful scrapes that must miss an event before a cancellation is the only
# reading left. Two: one miss is indistinguishable from the source omitting a row, and with
# the hour-long page cache a wrongly pruned event would flicker visibly.
MISSES_BEFORE_REMOVAL = 2

# The clock the sources print. Their times are naive strings off a Spanish listings page, so
# this is the only place that knows what they mean.
SPANISH_SCREEN_TIME = ZoneInfo("Europe/Madrid")


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
        """Process events unit by unit, reconciling each unit against what it covered."""
        event_count = 0
        # Events seen by any earlier unit of this run. A football match appears on both the
        # sport agenda and a team page; a unit must not count as missing what another unit
        # of the same run has already listed.
        self._run_seen_pks: set[int] = set()
        for unit in source.iter_units():
            seen: list[tuple[Any, bool]] = []
            for agenda_event in unit.events:
                saved = self.process_event(agenda_event)
                if saved is not None:
                    seen.append(saved)
                event_count += 1
            if not self.dry_run:
                self.reconcile_unit(unit, seen)
        if self.dry_run:
            self.stdout.write(f"  Total events: {event_count}")

    def reconcile_unit(self, unit: ScrapeUnit, seen: list[tuple[Any, bool]]) -> None:
        """Prune what the unit covered and did not list, with the caution each case earns.

        The rule, decided over the real data: a move brings its replacement in the same
        scrape, so a pairing whose listed count reaches what was already stored has its
        unlisted rows pruned at once; anything short of that is an omission or a
        cancellation, indistinguishable today, so it takes two consecutive misses — counted
        in successful scrapes, not hours, so the rule keeps its meaning if the scrape
        frequency changes. A doubleheader lists both rows and is never touched, which is
        the whole point of replacing the ±2-day window.
        """
        now = timezone.now()
        seen_pks = [event.pk for event, _ in seen]
        if seen_pks:
            StoredEvent.objects.filter(pk__in=seen_pks).update(last_seen_at=now, missing_scrapes=0)
        self._run_seen_pks.update(seen_pks)

        # No scope, an empty page or a parse that died halfway: a partial or undeclared
        # view of the world must not judge what is missing from it.
        if not unit.complete or not seen or not (unit.sport or unit.team_slug):
            return

        if unit.team_slug:
            scope = StoredEvent.objects.filter(
                Q(match__local__futbolenlatv_slug=unit.team_slug) | Q(match__visitor__futbolenlatv_slug=unit.team_slug)
            )
        else:
            scope = StoredEvent.objects.filter(competition__sport__name=unit.sport)

        seen_dates = [timezone.localdate(event.date) for event, _ in seen]
        candidates = list(
            scope.filter(
                date__gte=now,
                date__date__gte=min(seen_dates),
                date__date__lte=max(seen_dates),
            )
            .exclude(pk__in=self._run_seen_pks)
            .select_related("match", "race", "simpleevent")
        )
        if not candidates:
            return

        def group_key(child: Any) -> tuple:
            # Deliberately without the concrete type for name-based events: the same stage
            # has been stored as a Race by one vintage of the parser and a SimpleEvent by
            # another, and the pairing is the identity, not the Python class it landed in.
            if isinstance(child, Match):
                return ("match", child.competition_id, child.local_id, child.visitor_id)
            return ("byname", child.competition_id, child.name)

        seen_total: dict[tuple, int] = {}
        stored_before: dict[tuple, int] = {}
        seen_slots: set[tuple] = set()
        for event, created in seen:
            key = group_key(event)
            seen_total[key] = seen_total.get(key, 0) + 1
            seen_slots.add((key, event.date))
            if not created:
                stored_before[key] = stored_before.get(key, 0) + 1

        superseded, first_miss, removed = 0, 0, 0
        for candidate in candidates:
            child = candidate.child_event
            if child is None:
                continue
            key = group_key(child)
            # An unseen row whose exact slot — group and instant — a seen row occupies is a
            # duplicate by definition, whatever the counts say: the legacy twins this heals
            # differ only in detail text or concrete type.
            if (key, candidate.date) in seen_slots:
                candidate.delete()
                superseded += 1
                continue
            stored = stored_before.get(key, 0) + 1  # the unseen candidate itself
            if seen_total.get(key, 0) >= stored:
                candidate.delete()
                superseded += 1
            elif candidate.missing_scrapes + 1 >= MISSES_BEFORE_REMOVAL:
                candidate.delete()
                removed += 1
            else:
                StoredEvent.objects.filter(pk=candidate.pk).update(missing_scrapes=candidate.missing_scrapes + 1)
                first_miss += 1
        if superseded or first_miss or removed:
            label = unit.label or unit.sport or unit.team_slug or "unit"
            self.stdout.write(
                f"  [{label}] Reconciled: superseded={superseded}, "
                f"first_miss={first_miss}, removed_after_{MISSES_BEFORE_REMOVAL}_misses={removed}"
            )

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

    def process_event(self, agenda_event: Event) -> tuple[Any, bool] | None:
        """Process a single event, returning the stored row and whether it was created."""
        # In dry-run mode, just display the event
        if self.dry_run:
            self.display_event(agenda_event)
            return None

        sport = self.get_or_create_sport(agenda_event.sport)
        flag = self.get_or_create_flag(agenda_event.competition_crest)
        competition = self.get_or_create_competition(agenda_event.competition, sport, flag)

        # The source publishes Spanish screen time, so that is what the naive value means.
        # Pinned to Madrid rather than taken from `get_current_timezone()`: this has to say
        # what it means regardless of the setting, and it used to be read under `TIME_ZONE =
        # "UTC"`, where it applied no offset at all and stored the wall clock as though it
        # were UTC. `ZoneInfo` resolves summer or winter from the *event's* own date, not
        # from the day the scrape runs — the changeover routinely falls between the two.
        event_datetime = timezone.make_aware(agenda_event.datetime, timezone=SPANISH_SCREEN_TIME)

        event: Match | Race | SimpleEvent
        created: bool
        if isinstance(agenda_event.details, MatchDetails):
            event, created = self.save_match_event(competition, event_datetime, agenda_event.details)
        elif isinstance(agenda_event.details, RaceDetails):
            event, created = self.save_race_event(competition, event_datetime, agenda_event.details)
        elif isinstance(agenda_event.details, EventDetails):
            event, created = self.save_simple_event(competition, event_datetime, agenda_event.details)
        else:
            self.stderr.write(f"Unhandled event type: {agenda_event}")
            return None

        if not event:
            return None

        self.update_channels(event, agenda_event.channels)
        return event, created

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
    ) -> tuple[Any, bool]:
        """Store the event under its exact identity: the lookup plus its datetime.

        Deliberately no window. The previous version treated anything of the same pairing
        within ±2 days as the same event, which made a second fixture of the same pairing —
        an ACB doubleheader on the same court, an NBA back-to-back — impossible to store:
        219 such pairs exist in rows written before that window landed, none after it. And
        no smaller window is safe either: 99 of those 219 pairs sit under three hours
        apart. Closeness cannot distinguish a duplicate from two real games; only the
        source's current listing can, which is `reconcile_unit`'s job.

        Returns the event and whether it was created, which reconciliation needs: a moved
        fixture is one freshly created row plus one stored row nobody listed.
        """
        # Not `get_or_create`: the legacy duplicates this identity change heals — rows that
        # differ only in the detail text — still share a (lookup, datetime) slot, and
        # `get_or_create` raises on multiple matches. The freshest row wins; reconciliation
        # removes the others as unseen occupants of a seen slot.
        event = model.objects.filter(**lookup, date=event_datetime).order_by("-last_updated_at").first()
        if event is None:
            return model.objects.create(**lookup, date=event_datetime, **(defaults or {})), True

        changed = []
        for field, value in (defaults or {}).items():
            if getattr(event, field) != value:
                setattr(event, field, value)
                changed.append(field)
        if changed:
            event.save(update_fields=[*changed, "last_updated_at"])

        return event, False

    def save_simple_event(
        self, competition: Competition, event_datetime: datetime.datetime, details: EventDetails
    ) -> tuple[SimpleEvent, bool]:
        # `details` is the phase text ("Liga Regular", "1ª Ronda") and the source rephrases
        # it. Inside the lookup it was part of the identity, so every rephrasing created a
        # duplicate row: 234 of them existed in production when this moved to `defaults`.
        return self.upsert_event(
            SimpleEvent,
            {"competition": competition, "name": details.name},
            event_datetime,
            defaults={"details": details.details},
        )

    def save_race_event(
        self, competition: Competition, event_datetime: datetime.datetime, details: RaceDetails
    ) -> tuple[Race, bool]:
        return self.upsert_event(
            Race,
            {"competition": competition, "name": details.name},
            event_datetime,
            defaults={"details": details.details},
        )

    def save_match_event(
        self, competition: Competition, event_datetime: datetime.datetime, details: MatchDetails
    ) -> tuple[Match, bool]:
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
