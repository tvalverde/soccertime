"""What the workflow that runs on every push has to keep doing.

The suite is a thousand tests that nothing ever ran outside a laptop: the repository had no
`.github/` at all, so a push carrying a broken migration or an unformatted file looked
exactly like a good one until someone deployed it. This pins the parts of the workflow
whose loss is silent — a green run that checked less than it appears to.

Three of them cannot be seen by reading the log:

`DJANGO_DEBUG` is what lets the runner import the settings. Without a `DJANGO_SECRET_KEY`
they raise `ImproperlyConfigured` unless debug is on, and the key is deliberately not in
the repository, so dropping this variable breaks every step at once rather than the one
that lost it.

The integration marker excludes the tests that make real HTTP requests to the sites the
scraper reads. Included, CI would report this project broken on the day somebody else's
website went down, and the only defence against that is to stop believing CI.

`db/` is not in the repository — it is ignored — and it is where `DATABASES` puts the
SQLite file, so pytest-django creates its test database inside a directory that does not
exist on a fresh checkout. Nothing else in the run would say so.

The same workflow publishes the image production runs, which adds a fourth: the tag. The
deploy asks for `sha-<commit>` using the full hash `git rev-parse` prints, so a workflow
tagging with the abbreviated one would publish an image no deploy can name — and the failure
arrives on the server, at the pull, with the site still up and nothing else wrong.

Parsed with `re` rather than a YAML library, following `test_compose_images.py` and
`test_requirements.py`: a parser is not worth a dependency for a handful of fields.
"""

import re
from pathlib import Path

import pytest

from soccertime.tests.test_published_image import base_image_python_version

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def workflow() -> str:
    """The workflow with its comments dropped.

    Everything here reads it this way. The comments explain the very things these tests look
    for — the tag format, the excluded marker, why debug is set — so reading the file raw
    would let a workflow that describes all of it and does none of it pass. It is also how
    `python-version:` stops being an `on:` as far as a regex is concerned.
    """
    return "\n".join(line for line in WORKFLOW.read_text().splitlines() if not line.lstrip().startswith("#"))


def job(name: str) -> str:
    """The body of one job: every line indented deeper than the key that names it."""
    collected: list[str] = []
    inside = False
    for line in workflow().splitlines():
        if re.fullmatch(rf"  {name}:", line.rstrip()):
            inside = True
            continue
        if inside:
            if line.startswith("    ") or not line.strip():
                collected.append(line)
            else:
                break
    return "\n".join(collected)


class TestTheWorkflowIsReadable:
    """Guards every assertion below: a parser reading nothing would assert nothing."""

    def test_the_workflow_exists(self):
        assert WORKFLOW.is_file()

    @pytest.mark.parametrize("name", ["checks", "secrets", "publish"])
    def test_the_job_has_a_body(self, name):
        assert job(name).strip()


class TestItRunsWhereItMatters:
    def test_every_push_to_the_default_branch_is_checked(self):
        assert re.search(r"(?s)on:.*push:.*branches:.*main", workflow())

    def test_pull_requests_are_checked_too(self):
        """A branch that is merged without ever being pushed to `main` first."""
        assert re.search(r"(?m)^\s+pull_request:", workflow())


class TestItRunsEveryCheckTheProjectHas:
    @pytest.mark.parametrize(
        "command",
        [
            "ruff check soccertime/",
            "ruff format --check soccertime/",
            "mypy soccertime/",
            "pytest",
        ],
    )
    def test_the_command_is_part_of_the_run(self, command):
        assert command in job("checks")

    def test_the_suite_excludes_the_tests_that_call_other_people_websites(self):
        assert 'pytest -m "not integration"' in job("checks")

    def test_the_database_directory_exists_before_pytest_needs_it(self):
        """`db/` is ignored, and pytest-django puts its test database there."""
        run = job("checks")

        assert "mkdir -p db" in run
        assert run.index("mkdir -p db") < run.index("pytest")


class TestTheRunnerCanImportTheSettings:
    def test_debug_is_on_so_the_missing_secret_key_is_not_fatal(self):
        """The key is not in the repository; without debug, importing settings raises."""
        assert re.search(r'DJANGO_DEBUG:\s*"?true"?', job("checks"))


class TestThePythonIsTheOneProductionRuns:
    """The runner installs its own interpreter; the image brings its own. A suite that
    passes on one and would fail on the other reports nothing about the site.

    Pinned across the file boundary rather than written twice, the same way the deploy's
    settle time is pinned against the proxy's probe interval: raising the base image
    without raising this leaves CI testing an interpreter nothing runs.
    """

    def test_the_image_declares_a_version_to_match(self):
        assert base_image_python_version() is not None

    def test_the_runner_uses_it(self):
        assert f'python-version: "{base_image_python_version()}"' in job("checks")


class TestTheImageIsOnlyPublishedWhenItShouldBe:
    """Production pulls what this job pushes, so what it refuses to publish matters more
    than what it publishes."""

    def test_nothing_is_published_until_the_checks_have_passed(self):
        assert re.search(r"needs:\s*\[?\s*checks", job("publish"))

    def test_only_a_push_to_the_default_branch_publishes(self):
        """A pull request may come from a fork, and a fork must not be able to put an image
        where the deploy will find it — quite apart from its token being read-only."""
        condition = re.search(r"(?m)^\s+if:\s*(.+)$", job("publish"))

        assert condition
        assert "github.event_name == 'push'" in condition.group(1)
        assert "refs/heads/main" in condition.group(1)

    def test_it_asks_for_no_more_than_writing_a_package(self):
        """The workflow reads the repository; this one job also writes to the registry, and
        that difference is stated here rather than granted to everything."""
        granted = re.findall(r"(?m)^\s+([\w-]+):\s*(read|write)$", job("publish"))

        assert ("packages", "write") in granted
        assert ("contents", "write") not in granted


class TestTheScanForCommittedSecrets:
    """The half of secret scanning this repository is allowed to have.

    GitHub's own scanner covers partner and provider patterns on a free public repository;
    the category that would match a `DJANGO_SECRET_KEY` — generic patterns, previously called
    non-provider patterns — needs a paid Secret Protection licence. The REST API accepts the
    request to enable it, answers 200 and leaves it disabled, which is how this looked like a
    forgotten switch for a while rather than a licence.

    So this is a smoke alarm, not push protection: it reads the commits after they are pushed,
    and a key it finds is already public. What it buys is the difference between finding out
    in minutes and finding out never, and it also stops the leak travelling further — the
    publish job waits for it, so no image is built from a commit it flagged.
    """

    def test_it_can_see_the_history_it_is_meant_to_scan(self):
        """Actions checks out one commit by default, and a scanner pointed at a shallow clone
        finds nothing and says so cheerfully. This is the whole job, in one line of YAML."""
        assert "fetch-depth: 0" in job("secrets")

    def test_it_runs_the_scanner(self):
        assert "gitleaks/gitleaks-action" in job("secrets")

    def test_nothing_is_published_from_a_commit_it_flagged(self):
        """A leaked key in a tracked file would be inside the image as well as in the repo."""
        assert re.search(r"needs:\s*\[[^\]]*\bsecrets\b", job("publish"))


class TestTheTagTheDeployWillAskFor:
    def test_the_image_is_the_one_the_deploy_pulls(self):
        assert "ghcr.io/tvalverde/soccertime" in job("publish")

    def test_the_commit_tag_carries_the_whole_hash(self):
        """`git rev-parse HEAD` prints forty characters and the deploy asks for all of them;
        `type=sha` on its own publishes `sha-1234567`, which nothing would ever pull."""
        assert "type=sha,format=long" in job("publish")

    def test_the_published_image_carries_no_test_toolchain(self):
        """The production build is the one that says nothing: `INSTALL_DEV` defaults to
        false, and an image carrying pytest and mypy is not the one that was rehearsed."""
        assert "INSTALL_DEV" not in job("publish")
