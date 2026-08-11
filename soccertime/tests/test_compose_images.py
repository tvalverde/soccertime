"""The replica stack is `compose.yaml` plus overrides, so it must not inherit its service.

`compose.yaml` builds the development image with `INSTALL_DEV=true`; the local production
replica builds without it, which is the whole point of having a replica. Both used to be
tagged `soccertime:latest`, and bringing the replica up builds **both** services in one
command — so which image ended up under that tag depended on the order the builds finished.

It is not a theoretical race. After a replica build the development container came up on a
production image and `make test` died with `exec: "pytest": executable file not found`, which
reads like a broken environment rather than a tag collision. The reverse is quieter and worse:
start the replica without `--build` and it silently runs an image carrying the test and lint
toolchain, so the rehearsal stops rehearsing the thing being rehearsed.

Parsed with `re` rather than a YAML library, following `test_requirements.py`, which reads the
Dockerfile the same way: a parser is not worth a dependency for four fields.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEVELOPMENT = ROOT / "compose.yaml"
PRODUCTION = ROOT / "compose.production.yaml"
REPLICA = ROOT / "compose.production.local.yaml"

# The order `docker compose -f … -f … -f …` merges them in, which is the order the README
# documents for the replica.
REPLICA_STACK = [DEVELOPMENT, PRODUCTION, REPLICA]


def services(path):
    """Every service in a compose file, with the three fields these tests are about.

    Services sit at four spaces of indentation under `services:` and their keys at six, which
    is true of all three files and is asserted by the guard test below.
    """
    found = {}
    current = None
    in_profiles = False
    for line in path.read_text().splitlines():
        name = re.fullmatch(r"  ([a-z0-9-]+):", line.rstrip())
        if name:
            current, in_profiles = name.group(1), False
            found[current] = {}
            continue
        if current is None:
            continue
        if re.fullmatch(r"\s+profiles:", line.rstrip()):
            in_profiles = True
            found[current]["profiles"] = []
            continue
        entry = re.fullmatch(r"\s+- ([\w-]+)", line.rstrip()) if in_profiles else None
        if entry:
            found[current]["profiles"].append(entry.group(1))
            continue
        in_profiles = False
        for key, pattern in (
            ("image", r'\s+image:\s*"?([^"\s]+)"?'),
            ("install_dev", r'\s+INSTALL_DEV:\s*"?(\w+)"?'),
            ("healthcheck_host", r'\s+- "traefik\.http\.services\.[\w-]+\.loadbalancer\.healthcheck\.hostname=([^"]+)"'),
        ):
            match = re.fullmatch(pattern, line.rstrip())
            if match:
                found[current][key] = match.group(1)
    return found


def merged(paths):
    """What compose sees for the whole stack: later files override earlier ones by name."""
    result = {}
    for path in paths:
        for name, fields in services(path).items():
            result.setdefault(name, {}).update(fields)
    return result


def test_the_parser_finds_what_it_claims_to():
    """Guards every other assertion here: a parser reading nothing would assert nothing."""
    development = services(DEVELOPMENT)

    assert development["web"]["image"] == "soccertime:latest"
    assert development["web"]["install_dev"] == "true"
    assert services(REPLICA)["web"]["profiles"] == ["excluded-from-the-replica"]


def test_the_replica_and_the_development_image_are_different_tags():
    """The collision itself, in the stack that builds both services at once."""
    stack = merged(REPLICA_STACK)

    assert stack["web"]["image"] != stack["soccertime-web"]["image"]


@pytest.mark.parametrize("path", [DEVELOPMENT, PRODUCTION, REPLICA], ids=lambda p: p.name)
def test_no_tag_is_claimed_by_two_services_within_a_file(path):
    """The general form: one tag, one image, so a build can never be a race."""
    tags = [fields["image"] for fields in services(path).values() if "image" in fields]

    assert len(tags) == len(set(tags))


def test_the_replica_still_builds_without_the_toolchain():
    """The separation this protects. A replica carrying pytest is not a replica.

    Kept here rather than left to the earlier requirements test because the two failures look
    identical from the outside and have opposite causes: this one is about the build argument,
    the assertion above is about which image the argument ends up in.
    """
    assert merged(REPLICA_STACK)["soccertime-web"]["install_dev"] == "false"


class TestTheReplicaDoesNotRunTheDevelopmentServer:
    """The replica is `compose.yaml` plus overrides, so it inherited the `web` service.

    Every `up` therefore started a second Django on port 8000 and rebuilt its image, which is
    what put two builds behind one command in the first place. A profile nobody enables is how
    compose says "defined here, not started here": the service still merges, it simply is not
    part of this stack.

    Verified by running it rather than only by reading the file — with the profile in place,
    bringing the replica up leaves an already-running development container untouched instead
    of recreating it, and both stacks serve at once.
    """

    def test_the_development_service_is_profiled_out_of_the_replica(self):
        assert merged(REPLICA_STACK)["web"].get("profiles")

    def test_the_replica_still_runs_everything_it_needs(self):
        """Guards the test above: profiling out too much would also satisfy it."""
        stack = merged(REPLICA_STACK)

        assert not stack["soccertime-web"].get("profiles")
        assert not stack["soccertime-nginx"].get("profiles")
        assert not stack["traefik"].get("profiles")

    def test_the_development_stack_alone_still_starts_it(self):
        """A service only opts out where the profile is declared, so `compose.yaml` is intact.

        Putting the profile in `compose.yaml` would have been the obvious mistake: it would
        have stopped a plain `docker compose up` from starting anything at all.
        """
        assert not services(DEVELOPMENT)["web"].get("profiles")


class TestTheTraefikHealthCheck:
    """Traefik only stops sending traffic to a container that cannot serve if it asks first.

    That is what makes an overlapping deploy possible — measured, the difference between six
    seconds of 502-then-404 and a single failed request. It comes with a way to take the whole
    site down, which is why it is pinned here: the probe carries the container's IP as `Host`
    unless told otherwise, Django rejects it through ALLOWED_HOSTS, every server is marked down
    and the service answers **503 to everything**. Reproduced in the replica before the label
    was written.
    """

    def test_production_names_a_host_for_the_probe(self):
        assert services(PRODUCTION)["soccertime-web"].get("healthcheck_host")

    def test_the_replica_names_its_own(self):
        """Inheriting production's would fail every probe here and serve 503.

        `www.mojon.es` is not in the replica's ALLOWED_HOSTS, and nothing else would say so —
        the symptom is the whole site down, not a warning.
        """
        replica = services(REPLICA)["soccertime-web"].get("healthcheck_host")

        assert replica
        assert replica != services(PRODUCTION)["soccertime-web"]["healthcheck_host"]
