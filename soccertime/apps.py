import sys

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def load_initial_fixtures(sender, **kwargs):
    """Load initial fixtures after migrations on a fresh database.

    Skipped during test runs to avoid collisions with test fixtures.
    """
    if "pytest" in sys.modules:
        return

    from django.core.management import call_command

    from soccertime.models import Competition, Sport, Team

    # Only load fixtures if the database is empty (fresh install)
    if not Sport.objects.exists() and not Competition.objects.exists() and not Team.objects.exists():
        call_command("loaddata", "initial_data", verbosity=2)
        call_command("loaddata", "favorites", verbosity=2)


class SoccertimeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "soccertime"

    def ready(self):
        # Connect the signal to load fixtures after migrations
        post_migrate.connect(load_initial_fixtures, sender=self)
