"""What the workflow that publishes the apps has to keep doing.

The failure this file mostly exists for is silent. A signing config that finds no keystore is
not an error in Gradle: it is simply absent, and `assembleRelease` then writes
`app-mobile-release-unsigned.apk` instead of `app-mobile-release.apk` and reports success. A
workflow that trusted that would publish an unsigned APK — one Android refuses to install over
the previous version, so the reader has to uninstall, and uninstalling takes the favourites
with it, since they live on the device and nowhere else.

So the workflow verifies the signature rather than assuming it, and refuses outright when the
secret is missing. Both of those are asserted here, because both are lines somebody could
delete while tidying and nothing would go red until a release day.

The version is the other one. The tag is what a person reads the version off and the APK is
what a device reads it off; if they disagree, the wrong one is whichever nobody looks at. The
workflow compares them, which is only meaningful while the two applications agree with each
other — so that is checked here too, against the Gradle files themselves.

Parsed with `re` rather than a YAML library, following the other workflow tests.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / ".github" / "workflows" / "android-release.yml"
MODULES = ("app-mobile", "app-tv")


def workflow() -> str:
    """The workflow with its comments dropped, so a comment cannot satisfy an assertion."""
    return "\n".join(line for line in RELEASE.read_text().splitlines() if not line.lstrip().startswith("#"))


def version_of(module: str) -> str | None:
    build_file = ROOT / "android" / module / "build.gradle.kts"
    found = re.search(r'versionName\s*=\s*"([^"]+)"', build_file.read_text())
    return found.group(1) if found else None


class TestTheWorkflowIsReadable:
    """Guards every assertion below: a parser reading nothing would assert nothing."""

    def test_the_workflow_exists(self):
        assert RELEASE.is_file()

    def test_it_has_a_body(self):
        assert "runs-on:" in workflow()


class TestItRunsOnTheRightTag:
    def test_it_runs_on_a_tag_that_names_the_apps(self):
        """`v*` alone would be ambiguous: this repository is also a website."""
        assert re.search(r'(?s)on:.*tags:.*"android-v\*"', workflow())

    def test_it_does_not_run_on_every_push(self):
        body = workflow()
        assert not re.search(r"(?m)^\s+branches:", body)


class TestItRefusesToPublishSomethingNobodyCanInstall:
    def test_a_missing_keystore_secret_stops_it(self):
        """Gradle would otherwise write an unsigned APK and report success."""
        body = workflow()
        assert "ANDROID_KEYSTORE_B64" in body
        assert re.search(r'if \[ -z "\$KEYSTORE_B64" \]', body)
        assert "exit 1" in body

    def test_a_secret_that_arrives_empty_falls_back_instead_of_signing_with_it(self):
        """The fourth secret does not exist, and the build is meant not to need it.

        A PKCS12 keystore has one password, so `ANDROID_KEY_PASSWORD` is deliberately unset
        and the signing config falls back to the store's. What makes that fallback subtle is
        how a missing secret arrives: GitHub still sets the environment variable, to the empty
        string. `getenv` returns `""` and not null there, so a bare elvis never fires and the
        key would be signed with a blank password — while on a developer machine, where the
        variable is genuinely absent, the same expression works. Local success, release
        failure, and this workflow has never run.
        """
        for module in MODULES:
            build = (ROOT / "android" / module / "build.gradle.kts").read_text()
            found = re.search(r"keyPassword = ([^\n]+)", build)
            assert found, f"{module} declares no key password"
            expression = found.group(1)
            assert "ANDROID_KEY_PASSWORD" in expression, expression
            assert "isNotBlank" in expression or "isNullOrBlank" in expression, (
                f"{module} falls back only on null: {expression.strip()} — "
                "an absent secret arrives as an empty string, not as nothing"
            )

    def test_the_workflow_still_passes_the_optional_password(self):
        """So that adding the secret one day is enough, without editing the workflow too."""
        assert "ANDROID_KEY_PASSWORD" in workflow()

    def test_the_signature_is_verified_rather_than_assumed(self):
        """The call, not the word: `apksigner` also appears on the line that merely finds it."""
        assert re.search(r'apksigner"? verify', workflow())

    def test_it_verifies_against_the_oldest_device_it_ships_to(self):
        """A signature scheme the Fire TV cannot read is one it cannot install."""
        assert "--min-sdk-version 25" in workflow()

    def test_a_missing_signed_apk_is_an_error_and_not_an_empty_release(self):
        assert re.search(r'\[ -f "\$apk" \] \|\|', workflow())


class TestTheKeyNeverLandsWhereItCouldEscape:
    def test_it_is_written_outside_the_workspace_on_ci(self):
        """Anything inside the checkout can reach an artifact, a cache or a commit."""
        assert re.search(r"RUNNER_TEMP|runner\.temp", workflow())

    def test_the_workflow_never_writes_it_into_the_checkout(self):
        """`> release.jks` with no directory would land it beside the sources."""
        assert not re.search(r">\s*\.?/?release\.jks", workflow())

    # Whether a keystore on somebody's machine can be committed is asserted in
    # `test_ignore_rules.py`, which pins the `*.jks` and `*.keystore` patterns. Holding one
    # locally is how a release is built at all — the defect is committing it, not having it.


class TestTheVersionIsOneThing:
    @pytest.mark.parametrize("module", MODULES)
    def test_the_module_declares_a_version(self, module):
        assert version_of(module)

    def test_both_applications_agree(self):
        """The workflow compares the tag against these; two answers makes that meaningless."""
        declared = {module: version_of(module) for module in MODULES}
        assert len(set(declared.values())) == 1, declared

    def test_the_workflow_compares_the_tag_against_them(self):
        body = workflow()
        assert "GITHUB_REF_NAME#android-v" in body
        assert "versionName" in body


class TestItLeavesSomethingInstallable:
    def test_it_creates_a_release(self):
        assert "gh release create" in workflow()

    @pytest.mark.parametrize("name", ["soccertime-", "soccertime-tv-"])
    def test_both_apks_are_attached(self, name):
        assert f"{name}$version.apk" in workflow() or f'{name}"$version".apk' in workflow()
