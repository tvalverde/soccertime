"""How the application reaches production, once it is an image rather than an archive.

The deploy used to send the code: `git archive HEAD` into a tarball, scp, unpack it on the
server, build there. Everything about the running site was therefore decided on the server
at that moment — the base image resolved then, every wheel resolved then — and a rebuild of
the same commit was a different image, which is the whole reason the outgoing one is kept as
the rollback. The code also had to live there, next to the environment file, on a machine
whose only job is to serve.

Now CI publishes the image and the deploy pulls it. Three things about that are easy to lose
and expensive to lose:

The tag has to be the one CI publishes. The deploy asks for `sha-$(git rev-parse HEAD)`, all
forty characters; the workflow's `format=long` is what produces it. Abbreviate either side
and the pull fails on the server, mid-deploy.

The pull has to happen before anything on the server changes. It is the step most likely to
fail — the commit may not be published yet — and failing it after the database has been
snapshotted and the environment uploaded leaves work half done for no reason.

The pulled tag has to be dropped once the image is retagged. `prune-remote-images` reclaims
superseded images by pruning the dangling ones with this project's label; an image still
carrying its registry name is not dangling, so leaving the tag behind quietly turns the
prune into a no-op and the disk fills over releases rather than at once.

Asserted against the `Makefile` because that is where the production operations of this
project live, with the parser `test_database_transport.py` already uses for the same reason.
"""

import re

import pytest

from soccertime.tests.test_ci_workflow import workflow
from soccertime.tests.test_database_transport import MAKEFILE, recipe

# The steps of a deploy, in the order `deploy-production` names them.
DEPLOY_STEPS = ["pull_image", "upload-compose", "upload-config", "backup-remote-db", "remote_deploy"]


def prerequisites(target: str) -> list[str]:
    """The targets `make <target>` runs first, in order."""
    match = re.search(rf"(?m)^{re.escape(target)}:(.*)$", MAKEFILE.read_text())
    return match.group(1).split() if match else []


class TestTheMakefileIsReadable:
    """Guards the parser: a test reading nothing would assert nothing."""

    @pytest.mark.parametrize("target", ["pull_image", "remote_deploy"])
    def test_each_target_has_a_recipe(self, target):
        assert recipe(target).strip()

    def test_the_deploy_names_its_steps(self):
        assert prerequisites("deploy-production")


class TestTheImageArrivesFromTheRegistry:
    def test_the_deploy_pulls_it(self):
        assert "docker pull $(GHCR_IMAGE):$(DEPLOY_TAG)" in recipe("pull_image")

    def test_nothing_is_built_on_the_server(self):
        """A build there is what this replaces; it is also what put a `docker/dockerfile:1`
        download inside the container hand-over the site is served through."""
        assert not re.search(r"compose[^\n]*\bbuild\b", recipe("remote_deploy"))

    def test_the_code_is_no_longer_shipped(self):
        """The archive and its extraction, gone from both ends: the image carries the code
        now, and a server holding a copy of it can only ever be a stale one."""
        makefile = MAKEFILE.read_text()

        assert "git archive" not in makefile
        assert "$(ARCHIVE_NAME)" not in makefile

    def test_the_configuration_still_travels_with_the_deploy(self):
        """What the image cannot carry still has to reach the server; see the class below."""
        assert "upload-config" in prerequisites("deploy-production")


class TestWhatTheServerStillNeedsSent:
    """The image carries the code. It cannot carry the two files that say how to run it here.

    `.env.production` is the obvious one — it holds the secret key, which is why it is
    neither in the repository nor in a public image. The compose file is the one that is easy
    to miss and expensive to miss: the server's `~/docker/docker-compose.yml` does not define
    this service, it `include`s `compose.production.yaml` out of the uploaded directory. While
    the deploy shipped the whole archive that file came along with everything else. It no
    longer does, so a deploy that stopped sending it would go on running whichever definition
    was uploaded last — including one that still declares a `build:` pointing at code the
    server is no longer given. Nothing would report that: compose has no notion of a
    definition being out of date, and the container would come up and answer its health check.

    They travel by different targets on purpose. `upload-config` is also what
    `remote-apply-config` and the two admin toggles run, and those have no business replacing
    the definition of a running service — the admin is turned on to look at something, often
    while something else is wrong.
    """

    def test_the_environment_file_is_uploaded(self):
        assert "scp -P$(REMOTE_PORT) $(ENV_PROD_FILE) $(REMOTE_HOST):$(REMOTE_APP_PATH)/" in recipe("upload-config")

    def test_the_definition_is_uploaded_too(self):
        assert "upload-compose" in prerequisites("deploy-production")

    def test_the_definition_uploaded_is_the_one_belonging_to_the_image(self):
        """From git, at the commit being deployed, never from the working copy.

        The archive used to guarantee this by construction: it was made from `HEAD`, so the
        definition on the server was always the committed one. A plain `scp` of the working
        copy would put a half-finished compose edit into production without passing through
        git, review or CI — and on a rollback it would pair an old image with today's
        definition, which is the pairing nothing has ever run.
        """
        commands = recipe("upload-compose")

        assert "git show $(DEPLOY_COMMIT):$(COMPOSE_PROD_FILE)" in commands
        assert "scp -P$(REMOTE_PORT) $(COMPOSE_PROD_FILE)" not in commands

    def test_the_commit_it_comes_from_is_the_one_the_image_was_built_from(self):
        """`DEPLOY_TAG` is `sha-<commit>`; this is the same commit with the prefix removed,
        so overriding the tag for a rollback moves both the image and the definition."""
        assert re.search(r"(?m)^DEPLOY_COMMIT = \$\(DEPLOY_TAG:sha-%=%\)", MAKEFILE.read_text())

    def test_the_admin_toggles_do_not_replace_the_definition(self):
        """They upload an environment file and recreate the container; that is all they are."""
        assert "upload-compose" not in prerequisites("remote-apply-config")


class TestClearingTheCodeTheServerNoLongerRuns:
    """The deploy stopped sending code, so what it sent last is still lying there.

    Harmless as bytes — 2.8 MB of a checkout nothing reads — and misleading as evidence: it
    looks like the code production runs, and it is whatever commit was deployed the last time
    a deploy uploaded anything. Somebody reading it during an incident would be reading the
    past.

    What makes removing it delicate is that two files in that same directory are load-bearing,
    and neither looks it from there. The host's `~/docker/docker-compose.yml` does not define
    this service, it `include`s `compose.production.yaml` from here — and an `include` of a
    missing file fails every `docker compose` command on that machine, not only this one — and
    `.env.production` is where the container gets its secret key. So the target names what
    stays rather than what goes, and refuses to run at all if either is already absent, which
    is the state in which "delete everything else" would be a way to finish the job.
    """

    def test_the_two_files_the_host_reads_are_kept(self):
        commands = recipe("prune-remote-app-path")

        assert '! -name "$(COMPOSE_PROD_FILE)"' in commands
        assert '! -name "$(ENV_PROD_FILE)"' in commands

    def test_it_refuses_to_run_when_either_is_already_missing(self):
        """Guards the test above: keeping a file that is not there deletes the rest anyway."""
        commands = recipe("prune-remote-app-path")

        assert "test -f $(COMPOSE_PROD_FILE)" in commands
        assert "test -f $(ENV_PROD_FILE)" in commands
        assert "exit 1" in commands

    def test_it_cannot_reach_outside_the_application_directory(self):
        """`cd` first and search one level down from `.`, so no path it builds is absolute."""
        commands = recipe("prune-remote-app-path")

        assert "cd $(REMOTE_APP_PATH)" in commands
        assert "find . -mindepth 1 -maxdepth 1" in commands
        assert "rm -rf /" not in commands

    def test_it_says_what_it_is_about_to_remove(self):
        """A deletion nobody can read beforehand is one nobody can refuse."""
        commands = recipe("prune-remote-app-path")

        assert commands.index("-print") < commands.index("-exec rm -rf")


class TestTheTagIsTheOneThatWasPublished:
    def test_the_deploy_asks_for_the_commit_it_is_deploying(self):
        assert re.search(r"(?m)^DEPLOY_TAG \?= *sha-\$\(shell git rev-parse HEAD\)", MAKEFILE.read_text())

    def test_neither_side_abbreviates_it(self):
        """Seven characters on one side and forty on the other is a pull that fails on the
        server, mid-deploy, with the site up and nothing else wrong."""
        assert "rev-parse --short" not in MAKEFILE.read_text()
        assert "type=sha,format=long" in workflow()

    def test_the_registry_image_is_the_one_the_workflow_pushes(self):
        image = re.search(r"(?m)^GHCR_IMAGE \?= *(\S+)", MAKEFILE.read_text())

        assert image
        assert f"images: {image.group(1)}" in workflow()


class TestTheHostContractIsUnchanged:
    """`soccertime:latest` is what the compose file, the relay, the backups and the prune all
    name. The registry is transport: the pulled image is retagged and everything downstream
    goes on working, which is why none of those targets had to learn about a registry."""

    def test_the_pulled_image_becomes_the_tag_everything_else_names(self):
        assert "docker tag $(GHCR_IMAGE):$(DEPLOY_TAG) $(APP_NAME):latest" in recipe("remote_deploy")

    def test_the_outgoing_image_is_kept_as_the_rollback(self):
        assert "docker tag $(APP_NAME):latest $(APP_NAME):previous" in recipe("remote_deploy")

    def test_the_registry_name_is_dropped_once_it_has_been_retagged(self):
        """An image still carrying a registry name is not dangling, and the prune only
        reclaims dangling ones — so leaving it behind turns the prune into a no-op."""
        assert "docker rmi $(GHCR_IMAGE):$(DEPLOY_TAG)" in recipe("remote_deploy")

    def test_the_relay_is_handed_the_same_tag_it_always_was(self):
        assert "$(REMOTE_SOCCERTIME_SERVICE) $(APP_NAME):latest" in recipe("remote_deploy")


class TestNothingOnTheServerChangesBeforeTheImageIsThere:
    """The pull is the step most likely to fail — the commit may not be published yet — and
    failing it after the snapshots and the configuration upload leaves work half done."""

    @pytest.mark.parametrize("step", DEPLOY_STEPS[1:])
    def test_the_pull_comes_first(self, step):
        steps = prerequisites("deploy-production")

        assert steps.index("pull_image") < steps.index(step)

    def test_the_database_is_still_snapshotted_before_it_is_migrated(self):
        steps = prerequisites("deploy-production")

        assert steps.index("backup-remote-db") < steps.index("remote_deploy")
