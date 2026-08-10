from django.core.management.base import BaseCommand

from soccertime.models import Flag

from ._image_download import download_image


class Command(BaseCommand):
    help = "Re-download flag images whose file is missing from storage"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what is missing without downloading anything",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        missing = [
            flag
            for flag in Flag.objects.exclude(image="").exclude(image__isnull=True)
            if not flag.image.storage.exists(flag.image.name)
        ]

        if not missing:
            self.stdout.write(self.style.SUCCESS("Every flag image is present."))
            return

        self.stdout.write(f"Flags whose file is missing: {len(missing)}")

        if dry_run:
            for flag in missing:
                self.stdout.write(f"  {flag.image.name} <- {flag.name}")
            self.stdout.write(self.style.WARNING("Dry run: nothing downloaded"))
            return

        restored = 0
        for flag in missing:
            # Flag.name holds the URL the image was originally fetched from.
            image = download_image(flag.name, on_error=self.stderr.write)
            if not image:
                self.stderr.write(f"  Could not restore {flag.display_name or flag.name}")
                continue
            flag.save_flag(image, flag.name)
            restored += 1

        self.stdout.write(self.style.SUCCESS(f"Restored {restored} of {len(missing)} flag images"))
        if restored < len(missing):
            self.stdout.write(self.style.WARNING(f"Still missing: {len(missing) - restored}"))
