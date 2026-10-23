"""When the smoke test fails, it points at the component that actually failed.

On 2026-10-23 a Docker upgrade recreated the daemon's socket while the socket proxy kept the
old one bind-mounted, so Traefik could no longer see any container. The relay retired the one
it still routed to, and every page answered 503 from the proxy while the new container was
healthy and had not received a single request. The smoke test said "the deploy is live and
broken" and offered a database restore, which would have changed nothing.

`wait-remote-healthy` runs first, so by the time a page is fetched every container is known
to be healthy. A failure made only of statuses the proxy sends on its own — no connection,
no router, no live server, a gateway error — is therefore the proxy's, and the message says
so. Any other status came from the application, and the message about the release stands.

The recipe runs here as `make` would run it, by `/bin/sh`, against a stand-in `curl` that
answers each path with the status a test names. `make` itself is not in the image the suite
runs in, so the recipe is lifted from the Makefile rather than invoked through it.
"""

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

from soccertime.tests.test_database_transport import MAKEFILE, recipe

PRODUCTION_URL = "https://example.test/soccertime"
SMOKE_PATHS = "/healthz/ /agenda/"

FAKE_CURL = """#!/bin/sh
for argument; do url=$argument; done
path=${url#"$PRODUCTION_URL"}
path=${path%%\\?*}
code=200
for pair in $SMOKE_RESPONSES; do
    [ "${pair%%=*}" = "$path" ] && code=${pair#*=}
done
printf %s "$code"
"""

PROXY_HINT = "make remote-proxy-logs"
RELEASE_HINT = "The deploy is live and broken"


def page_check() -> str:
    """The shell command of `remote-smoke-test` that fetches the pages, as `make` hands it over."""
    body = recipe("remote-smoke-test")
    match = re.search(r"(?ms)^\t@(failed=.*?Smoke test passed\.\")$", body)
    assert match, "remote-smoke-test no longer checks the pages in one command"
    command = match.group(1).replace("\n\t", "\n")
    command = command.replace("$(PRODUCTION_URL)", PRODUCTION_URL).replace("$(SMOKE_PATHS)", SMOKE_PATHS)
    assert "$(" not in command.replace("$$(", ""), "the check reads a make variable this test does not set"
    return command.replace("$$", "$")


@pytest.fixture
def fetch(tmp_path: Path):
    """Run the page check against a `curl` answering each path as `responses` says."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(FAKE_CURL)
    curl.chmod(curl.stat().st_mode | stat.S_IXUSR)

    def run(responses: dict[str, str]) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "PRODUCTION_URL": PRODUCTION_URL,
            "SMOKE_RESPONSES": " ".join(f"{path}={code}" for path, code in responses.items()),
        }
        return subprocess.run(["/bin/sh", "-c", page_check()], env=env, capture_output=True, text=True)

    return run


def test_every_page_answering_passes(fetch):
    result = fetch({})

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Smoke test passed." in result.stdout


@pytest.mark.parametrize("code", ["000", "404", "502", "503", "504"])
def test_a_status_only_the_proxy_sends_points_at_the_proxy(fetch, code):
    result = fetch({"/healthz/": code, "/agenda/": code})

    assert result.returncode == 1
    assert PROXY_HINT in result.stdout
    assert RELEASE_HINT not in result.stdout


def test_a_status_the_application_sent_points_at_the_release(fetch):
    result = fetch({"/healthz/": "503", "/agenda/": "500"})

    assert result.returncode == 1
    assert RELEASE_HINT in result.stdout
    assert PROXY_HINT not in result.stdout


def test_the_release_hint_no_longer_offers_a_database_restore_as_the_rollback(fetch):
    """Restoring the database undoes a migration, not a release; the image is the rollback."""
    result = fetch({"/agenda/": "500"})

    assert "DEPLOY_TAG=sha-" in result.stdout
    assert "only if this release migrated it" in result.stdout


def test_the_proxy_logs_target_exists():
    assert re.search(r"(?m)^remote-proxy-logs:", MAKEFILE.read_text())


def test_every_option_the_logs_help_names_is_one_the_recipe_reads():
    """`SINCE=10m` was documented while the recipe read `LOG_SINCE`, so it filtered nothing."""
    help_line = re.search(r"remote-logs +Read the application log \(([^)]*)\)", MAKEFILE.read_text())
    assert help_line, "the help no longer documents remote-logs' options"
    options = re.findall(r"\b([A-Z]+)=", help_line.group(1))
    assert options

    body = recipe("remote-logs")
    for option in options:
        assert f"$({option})" in body, f"remote-logs documents {option}= but never reads it"
