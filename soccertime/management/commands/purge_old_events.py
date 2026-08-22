import datetime
from argparse import ArgumentParser
from typing import Any

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date

from soccertime.models import Event

DEFAULT_RETENTION_DAYS = 90


class Command(BaseCommand):
    help = "Purge historical sporting events older than a specified retention threshold."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_RETENTION_DAYS,
            help=f"Number of days of event history to retain (default: {DEFAULT_RETENTION_DAYS})",
        )
        parser.add_argument(
            "--before-date",
            type=str,
            default=None,
            help="Explicit cutoff date (YYYY-MM-DD). Events strictly before this date will be purged.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Display the number and breakdown of events that would be deleted without deleting them.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days = options["days"]
        before_date_str = options["before_date"]
        dry_run = options["dry_run"]

        if before_date_str:
            parsed = parse_date(before_date_str)
            if not parsed:
                raise CommandError(f"Invalid date format: {before_date_str}. Use YYYY-MM-DD.")
            cutoff = timezone.make_aware(
                datetime.datetime.combine(parsed, datetime.time.min),
                timezone.get_current_timezone(),
            )
        else:
            if days < 0:
                raise CommandError("--days must be a positive integer.")
            cutoff = timezone.now() - datetime.timedelta(days=days)

        old_events = Event.objects.filter(date__lt=cutoff)
        total_candidates = old_events.count()

        self.stdout.write(f"Cutoff date: {cutoff.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        self.stdout.write(f"Events eligible for purging (date < cutoff): {total_candidates}")

        if total_candidates == 0:
            self.stdout.write(self.style.SUCCESS("No historical events match the purge criteria. Database is clean."))
            return

        # Breakdown by sport
        sport_breakdown = old_events.values("competition__sport__name").annotate(total=Count("id")).order_by("-total")
        self.stdout.write("\nBreakdown by sport:")
        for item in sport_breakdown:
            sport_name = item["competition__sport__name"] or "Unknown"
            self.stdout.write(f"  - {sport_name}: {item['total']} events")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"\n[DRY RUN] Would delete {total_candidates} historical events. No changes made.")
            )
            return

        deleted_count, details = old_events.delete()
        cache.clear()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully purged {deleted_count} records ({total_candidates} events) from the database."
            )
        )
