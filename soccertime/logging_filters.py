"""Keeping the access log about visitors rather than about the monitoring.

Two probes hit `/healthz/` constantly: Traefik's load-balancer health check every second —
which is what lets a deploy hand over between containers without dropping requests — and the
container's own health check every thirty. Measured on production, that is **89,280 access
lines a day, 97% of the log**. The json-file driver rotates at 10 MB × 3, so a real error is
pushed out of `docker logs` long before it would otherwise be, and `make remote-error-check`
scans a log that is almost entirely probe traffic.
"""

import logging
from typing import Any

# Matched at the end of the path, not the start. uvicorn is run with `--root-path /soccertime`
# and includes it in `scope["path"]`, so the line it logs reads `/soccertime/healthz/` even
# for the container's own probe of `http://localhost:8000/healthz/`. Anchoring at the start
# matched nothing in production while every unit test passed — the real stack is what caught
# it, and matching the suffix covers the path with or without the prefix.
HEALTH_PATH = "/healthz/"

# uvicorn logs an access line as '%s - "%s %s HTTP/%s" %d' with
# (client, method, path, http_version, status) — the path at index 2, the status at 4.
PATH_INDEX = 2
STATUS_INDEX = 4
EXPECTED_ARGS = 5


class SkipSuccessfulHealthChecks(logging.Filter):
    """Drop the access line for a health probe, but only while it is passing.

    The conditional half is the point. Silencing `/healthz/` outright would also silence the
    probe starting to fail, which is precisely what someone reading this log needs to see —
    a health check answering 500 is how the site went down twice before, once with the
    container reporting healthy the whole time. So the noise goes and the evidence stays.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args: Any = record.args
        if not isinstance(args, tuple) or len(args) != EXPECTED_ARGS:
            # Not the access line this filter knows about: uvicorn changed its format, or
            # something else logged here. Letting it through is the safe direction.
            return True
        path, status = args[PATH_INDEX], args[STATUS_INDEX]
        if not isinstance(path, str):
            return True
        if not path.split("?", 1)[0].endswith(HEALTH_PATH):
            return True
        return not (isinstance(status, int) and 200 <= status < 300)
