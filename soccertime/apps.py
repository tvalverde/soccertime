import logging
import sys
from typing import Any

from django.apps import AppConfig
from django.db.models.signals import post_migrate

from soccertime.logging_filters import SkipSuccessfulHealthChecks


def load_initial_fixtures(sender: type[AppConfig], **kwargs: Any) -> None:
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


def attach_health_check_filter() -> None:
    """Quieten the passing health probes in uvicorn's access log.

    Added to the existing logger rather than declared in a `LOGGING` setting, and that is
    the whole point of doing it here. `dictConfig` does not merge: naming `uvicorn.access`
    under `loggers` resets every key left unspecified, so a config that supplied only
    `filters` **cleared uvicorn's handler** and silenced the access log completely. Measured
    on the replica before this was noticed — the filter was attached and nothing was logged
    at all, real requests included.
    """
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(existing, SkipSuccessfulHealthChecks) for existing in logger.filters):
        logger.addFilter(SkipSuccessfulHealthChecks())


class SoccertimeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "soccertime"

    def ready(self) -> None:
        # Connect the signal to load fixtures after migrations
        post_migrate.connect(load_initial_fixtures, sender=self)
        attach_health_check_filter()
