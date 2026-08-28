"""The limit on how fast one caller may read.

An events listing runs `icontains` across six joined tables in SQLite, and the API answers
without a session, a key or anything else to identify who is asking — so the only thing
between a script and the container that also serves the database is this.

The counters are kept in a cache of their own. Both stores are file-based in production and
Django culls one once it holds three hundred entries, so counting requests in the page cache
would evict the rendered pages it exists to keep. Where no such cache is configured — the
development container and the test suite both run without one — this falls back to the
default cache, which is how it stays inert there rather than failing on import.
"""

from typing import Any

from django.core.cache import InvalidCacheBackendError, caches
from rest_framework.settings import api_settings
from rest_framework.throttling import AnonRateThrottle


class ApiRateThrottle(AnonRateThrottle):
    scope = "api"

    @property
    def cache(self) -> Any:
        """Resolved per request rather than bound at import, so a test can swap it."""
        try:
            return caches["throttling"]
        except InvalidCacheBackendError:
            return caches["default"]

    def get_rate(self) -> str:
        """Read the configured rate now, rather than the copy taken when DRF was imported.

        `SimpleRateThrottle.THROTTLE_RATES` is a class attribute bound to the settings
        dictionary at import time, so changing the rate afterwards changes nothing — which
        is also what made the limit untestable.
        """
        return str(api_settings.DEFAULT_THROTTLE_RATES[self.scope])
