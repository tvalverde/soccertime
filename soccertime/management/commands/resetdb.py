"""
Management command to reset the database.
This is useful for development and testing.
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
import os


class Command(BaseCommand):
    help = "Reset the database by deleting it and running migrations again"

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        db_path = settings.DATABASES["default"]["NAME"]

        if not options["noinput"]:
            confirm = input(f"This will delete the database at {db_path}. Are you sure? [y/N]: ")
            if confirm.lower() != "y":
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

        # Delete the database file if it exists
        if os.path.exists(db_path):
            os.remove(db_path)
            self.stdout.write(self.style.SUCCESS(f"Deleted database: {db_path}"))
        else:
            self.stdout.write(self.style.WARNING(f"Database not found: {db_path}"))

        # Run migrations
        self.stdout.write(self.style.MIGRATE_HEADING("Running migrations..."))
        call_command("migrate", verbosity=1)

        self.stdout.write(self.style.SUCCESS("Database reset complete!"))
        self.stdout.write("Initial fixtures have been automatically loaded.")
