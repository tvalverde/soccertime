from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Q

from soccertime.models import Flag, Team

from ._image_download import download_image


def missing_files(queryset: Any, field_name: str) -> list[Any]:
    """Rows whose image field points at a file that is not in storage."""
    return [
        instance
        for instance in queryset.exclude(**{field_name: ""}).exclude(**{f"{field_name}__isnull": True})
        if not getattr(instance, field_name).storage.exists(getattr(instance, field_name).name)
    ]


class Command(BaseCommand):
    help = "Report broken image references and restore the flag files that can be re-fetched"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what is missing without downloading anything",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        self.report_crests()
        self.restore_flags(dry_run=options["dry_run"])

    def report_crests(self) -> None:
        """Crests are reported, never restored: `Team` keeps no source URL.

        A missing crest only comes back when the team appears in a scrape again, which
        supplies the URL. Meanwhile the page renders the fallback icon, so nothing breaks.
        """
        broken = missing_files(Team.objects, "crest")
        without_crest = Team.objects.filter(Q(crest="") | Q(crest__isnull=True)).count()

        self.stdout.write("Crests:")
        self.stdout.write(f"  teams whose crest file is missing: {len(broken)}")
        self.stdout.write(f"  teams with no crest at all:        {without_crest}")
        if broken or without_crest:
            self.stdout.write("  (recovered automatically the next time those teams are scraped)")

    def restore_flags(self, dry_run: bool) -> None:
        broken = missing_files(Flag.objects, "image")

        self.stdout.write("Flags:")
        self.stdout.write(f"  flags whose file is missing: {len(broken)}")
        if not broken:
            return

        if dry_run:
            for flag in broken:
                self.stdout.write(f"    {flag.image.name} <- {flag.name}")
            self.stdout.write(self.style.WARNING("Dry run: nothing downloaded"))
            return

        restored = 0
        for flag in broken:
            # Flag.name holds the URL the image was originally fetched from.
            image = download_image(flag.name, on_error=self.stderr.write)
            if not image:
                self.stderr.write(f"  Could not restore {flag.display_name or flag.name}")
                continue
            flag.save_flag(image, flag.name)
            restored += 1

        self.stdout.write(self.style.SUCCESS(f"  Restored {restored} of {len(broken)} flag images"))
        if restored < len(broken):
            self.stdout.write(self.style.WARNING(f"  Still missing: {len(broken) - restored}"))
