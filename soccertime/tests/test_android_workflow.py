"""What the workflow that builds the Android apps has to keep doing.

`android.yml` is filtered by `paths`, because nothing under `android/` can break the Django
suite and nothing in the Django tree can break the apps — making either wait for the other
only buys slower feedback. That filter is cheap and obvious.

The expensive part is what it must *not* do to `ci.yml`, and it is the reason this file
exists. The natural next thought after adding a filtered workflow is to filter the old one
too, so a commit touching only `android/` stops running the Python suite it cannot affect.
That change would be silent, would look like a tidy-up, and would turn secret scanning off
for the whole Android tree: the `secrets` job lives in `ci.yml`, it reads what each push
carries, and `publish` waits for it. A key committed under `android/` — a keystore password,
a signing config someone pasted — would reach a public repository with nothing looking at it.

So `ci.yml` deliberately runs on every push and pull request, filtered by nothing, and that
is asserted here rather than left to a comment somebody will delete.

Parsed with `re` rather than a YAML library, following `test_ci_workflow.py`,
`test_compose_images.py` and `test_requirements.py`: a parser is not worth a dependency for
a handful of fields.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
ANDROID = WORKFLOWS / "android.yml"
CI = WORKFLOWS / "ci.yml"
CATALOG = ROOT / "android" / "gradle" / "libs.versions.toml"


def without_comments(path: Path) -> str:
    """The workflow with its comments dropped.

    The comments here explain the very things these tests look for — why `ci.yml` carries no
    filter, why the artifact is kept — so reading the file raw would let one that describes
    all of it and does none of it pass.
    """
    return "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("#"))


def trigger_block(path: Path) -> str:
    """The body of `on:`: every line indented under it, up to the next top-level key."""
    collected: list[str] = []
    inside = False
    for line in without_comments(path).splitlines():
        if re.fullmatch(r"on:", line.rstrip()):
            inside = True
            continue
        if inside:
            if line.startswith(" ") or not line.strip():
                collected.append(line)
            else:
                break
    return "\n".join(collected)


class TestTheWorkflowIsReadable:
    """Guards every assertion below: a parser reading nothing would assert nothing."""

    def test_the_workflow_exists(self):
        assert ANDROID.is_file()

    def test_it_declares_when_it_runs(self):
        assert trigger_block(ANDROID).strip()

    def test_the_django_workflow_declares_when_it_runs_too(self):
        assert trigger_block(CI).strip()


class TestSecretScanningStillReadsTheAndroidTree:
    """The one this file is for."""

    @pytest.mark.parametrize("filter_key", ["paths", "paths-ignore"])
    def test_the_django_workflow_is_filtered_by_nothing(self, filter_key):
        assert not re.search(rf"(?m)^\s+{re.escape(filter_key)}:", trigger_block(CI)), (
            f"`{filter_key}` in ci.yml stops gitleaks reading pushes that touch only android/"
        )

    def test_the_django_workflow_still_runs_on_every_push_and_pull_request(self):
        block = trigger_block(CI)
        assert re.search(r"(?s)push:.*branches:.*main", block)
        assert re.search(r"(?m)^\s+pull_request:", block)


class TestItRunsWhereItMatters:
    def test_pushes_to_the_default_branch_are_built(self):
        assert re.search(r"(?s)push:.*branches:.*main", trigger_block(ANDROID))

    def test_pull_requests_are_built_too(self):
        """A branch merged without ever being pushed to `main` first."""
        assert re.search(r"(?m)^\s+pull_request:", trigger_block(ANDROID))

    @pytest.mark.parametrize("watched", ["android/**", ".github/workflows/android.yml"])
    def test_it_watches_what_can_change_the_apps(self, watched):
        assert watched in trigger_block(ANDROID)

    def test_it_watches_nothing_else(self):
        """A path filter that also matched the Django tree would rebuild the apps for nothing."""
        listed = re.findall(r'(?m)^\s+- "([^"]+)"', trigger_block(ANDROID))
        assert listed
        assert all(path.startswith(("android/", ".github/workflows/android")) for path in listed)


class TestItRunsEveryCheckTheAppsHave:
    @pytest.mark.parametrize("task", ["lint", "testDebugUnitTest", "assembleDebug"])
    def test_the_gradle_task_is_part_of_the_run(self, task):
        assert f"./gradlew {task}" in without_comments(ANDROID)

    def test_it_runs_them_from_the_project_directory(self):
        """`./gradlew` does not exist at the repository root; the build lives one level down."""
        assert re.search(r"(?m)^\s+working-directory:\s*android\s*$", without_comments(ANDROID))

    def test_the_wrapper_it_runs_is_the_one_in_the_repository(self):
        assert (ROOT / "android" / "gradlew").is_file()


class TestTheToolchainIsPinned:
    def test_a_java_version_is_chosen_rather_than_inherited(self):
        """Whatever the runner image happens to ship is not a version this project picked."""
        assert re.search(r'(?m)^\s+java-version:\s*"\d+"', without_comments(ANDROID))

    def test_the_catalog_dependabot_watches_is_here(self):
        """`test_dependency_updates.py` names this file; a build without it is unwatched."""
        assert CATALOG.is_file()


class TestTheBuildLeavesSomethingInstallable:
    def test_the_debug_apks_are_kept(self):
        """The TLS handshake on Android 7.1 can only be proven by sideloading one."""
        body = without_comments(ANDROID)
        assert "upload-artifact" in body
        assert re.search(r"(?m)^\s+path:.*\.apk\s*$", body)

    def test_an_empty_upload_fails_the_run(self):
        """Uploading nothing is the default, and it looks exactly like uploading something."""
        assert re.search(r"(?m)^\s+if-no-files-found:\s*error\s*$", without_comments(ANDROID))
