"""Which paths the proxy routes on their own, and which of those it slows down.

The application's own throttle refuses a caller inside Python, which means every refusal
still costs a process, a thread and a request cycle. A limit at the proxy refuses at the
edge, and it is the only one that stands between a flood and the container — so the routes
worth protecting get a router of their own, and a router of their own is exactly what can
be got wrong: forget the strip-prefix middleware and Django receives `/soccertime/api/...`,
which resolves to nothing and answers 404 to the whole API. Miss the priority and the
catch-all router wins, so the rate limit is defined and never applied.

Neither mistake shows up in a smoke test that only asks whether the page loads — the
symptom of the second is nothing at all. So the label sets are compared here instead.

Parsed with `re` rather than a YAML library, following `test_compose_images.py`, which
reads these same files that way.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ROOT / "compose.production.yaml"
REPLICA = ROOT / "compose.production.local.yaml"

ROUTER = re.compile(r"traefik\.http\.routers\.(?P<router>[\w-]+)\.(?P<key>[\w.]+)=(?P<value>[^\"\n]*)")
MIDDLEWARE = re.compile(r"traefik\.http\.middlewares\.(?P<name>[\w-]+)\.(?P<key>[\w.]+)=(?P<value>[^\"\n]*)")

# The order the proxy must try them in: the most specific prefix first, the catch-all last.
EXPECTED_ORDER = ["soccertime-nginx", "soccertime-admin", "soccertime-favorite", "soccertime-api", "soccertime-app"]

RATE_LIMITED = ["soccertime-admin", "soccertime-favorite", "soccertime-api"]


def routers(path):
    """Every router the file configures, as {router: {key: value}}."""
    found: dict[str, dict[str, str]] = {}
    for match in ROUTER.finditer(path.read_text()):
        found.setdefault(match["router"], {})[match["key"]] = match["value"]
    return found


def middlewares(path):
    found: dict[str, dict[str, str]] = {}
    for match in MIDDLEWARE.finditer(path.read_text()):
        found.setdefault(match["name"], {})[match["key"]] = match["value"]
    return found


class TestTheFilesAreReadable:
    """Guards the parser: a test that read nothing would assert nothing."""

    def test_production_configures_the_routers_this_file_talks_about(self):
        assert set(EXPECTED_ORDER) <= set(routers(PRODUCTION))


class TestTheApiIsRoutedOnItsOwn:
    def test_it_answers_on_its_own_prefix(self):
        assert "PathPrefix(`/soccertime/api`)" in routers(PRODUCTION)["soccertime-api"]["rule"]

    def test_it_still_strips_the_prefix(self):
        """Without this Django is handed `/soccertime/api/...` and answers 404 to all of it."""
        assert "soccertime-app-strip-prefix" in routers(PRODUCTION)["soccertime-api"]["middlewares"]

    def test_it_is_served_by_the_application(self):
        assert routers(PRODUCTION)["soccertime-api"]["service"] == "soccertime-app-service"

    def test_it_is_reached_over_tls_like_every_other_route(self):
        configured = routers(PRODUCTION)["soccertime-api"]

        assert configured["entrypoints"] == "websecure"
        assert configured["tls"] == "true"


class TestTheRateLimits:
    @pytest.mark.parametrize("router", RATE_LIMITED)
    def test_each_protected_route_carries_one(self, router):
        applied = routers(PRODUCTION)[router]["middlewares"]

        assert f"{router}-rate-limit" in applied

    @pytest.mark.parametrize("router", RATE_LIMITED)
    def test_each_limit_is_fully_specified(self, router):
        """A rate limit missing its period is not a smaller limit, it is a different one."""
        limit = middlewares(PRODUCTION)[f"{router}-rate-limit"]

        assert {"ratelimit.average", "ratelimit.period", "ratelimit.burst"} <= set(limit)

    def test_the_api_is_allowed_more_than_the_application_itself_grants(self):
        """The proxy is a backstop, not the primary control.

        The application counts 30 a minute per caller and answers 429 to the rest, which is
        cheap but not free. This caps how fast it can be made to do even that, and sits
        above it so it never refuses a caller the application would have served.
        """
        limit = middlewares(PRODUCTION)["soccertime-api-rate-limit"]

        assert int(limit["ratelimit.average"]) > 30
        assert limit["ratelimit.period"] == "1m"


class TestThePriorities:
    def test_the_more_specific_prefix_always_wins(self):
        configured = routers(PRODUCTION)
        priorities = [int(configured[router]["priority"]) for router in EXPECTED_ORDER]

        assert priorities == sorted(priorities, reverse=True)

    def test_no_two_routers_share_a_priority(self):
        """Traefik picks between equal priorities by rule length, which nobody is reading."""
        priorities = [int(configured["priority"]) for configured in routers(PRODUCTION).values()]

        assert len(priorities) == len(set(priorities))


class TestTheReplicaRehearsesTheRouting:
    """The replica exists so routing changes are tried before production sees them.

    It answers on a different host, so every router needs its rule restated there. One that
    is not is not rehearsed at all — it inherits a rule built from an environment variable
    the replica deliberately does not rely on.
    """

    @pytest.mark.parametrize("router", EXPECTED_ORDER)
    def test_every_production_router_is_routed_locally_too(self, router):
        assert "rule" in routers(REPLICA).get(router, {})

    @pytest.mark.parametrize("router", EXPECTED_ORDER)
    def test_the_local_rule_answers_on_the_replica_host(self, router):
        assert "Host(`mojon.local`)" in routers(REPLICA)[router]["rule"]
