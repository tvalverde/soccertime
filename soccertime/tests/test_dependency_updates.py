"""Every kind of dependency this repository pins has something watching it.

Twelve pinned production dependencies — Django, DRF and Pillow among them — and nothing
ever proposed an update to any of them: Dependabot was off, so a published advisory reached
this project only if somebody happened to read about it. Pinning is what makes the builds
reproducible and it is also what makes them stale, and the two go together.

The interesting failure is not a missing file, it is a file that covers less than the
repository holds. So the expectation is derived from what is actually here rather than
written down twice: a manifest of a kind Dependabot understands, with no entry for that
ecosystem, is the state this test exists to refuse. Pinning the base image (see
`test_published_image.py`) is exactly the change that added such a manifest.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "dependabot.yml"

# The manifests this repository keeps, and the ecosystem Dependabot reads each one with.
ECOSYSTEM_OF = {
    "pip": list(ROOT.glob("requirements*.txt")),
    "github-actions": list((ROOT / ".github" / "workflows").glob("*.yml")),
    "docker": [ROOT / "Dockerfile"],
    # The Android project's version catalog. Every version the two apps pin — the Gradle
    # plugin, Kotlin, Compose, OkHttp — is written there and nowhere else, so watching this
    # one file watches the whole of it.
    "gradle": [ROOT / "android" / "gradle" / "libs.versions.toml"],
}


def declared_ecosystems() -> list[str]:
    return re.findall(r"(?m)^\s+- package-ecosystem:\s*\"?([\w-]+)\"?", CONFIG.read_text())


def test_the_configuration_is_readable():
    """Guards the assertions below: a parser reading nothing would assert nothing."""
    assert CONFIG.is_file()
    assert declared_ecosystems()


@pytest.mark.parametrize("ecosystem", sorted(ECOSYSTEM_OF))
def test_the_manifests_of_that_kind_are_still_here(ecosystem):
    """Guards the test below: an ecosystem covering nothing would be a pointless entry."""
    assert [path for path in ECOSYSTEM_OF[ecosystem] if path.is_file()]


@pytest.mark.parametrize("ecosystem", sorted(ECOSYSTEM_OF))
def test_every_kind_of_manifest_is_watched(ecosystem):
    assert ecosystem in declared_ecosystems()


def test_the_updates_are_scheduled():
    """An entry with no schedule is a section Dependabot refuses to load."""
    assert len(re.findall(r"(?m)^\s+interval:", CONFIG.read_text())) == len(declared_ecosystems())


# The one version this repository refuses to be offered, read from the configuration rather
# than written down a second time here, so the two cannot say different things.
IGNORED_DJANGO = re.compile(r'dependency-name:\s*"django"\s*\n\s*versions:\s*\[">=([\d.]+)"\]')


def django_ceiling() -> str | None:
    found = IGNORED_DJANGO.search(CONFIG.read_text())
    return found.group(1) if found else None


def test_the_django_ceiling_is_still_a_wall():
    """Says when the reason for holding Django back has stopped being true.

    `django-admin-sortable2` swaps the admin's `actions.js` for a copy named after the running
    Django, and the release installed here ships nothing for 6.1 — which is why `dependabot.yml`
    ignores that version and above, and why Dependabot stops proposing it every week.

    An ignore nobody revisits is how a project stays three versions behind for years. The
    package will catch up on some release, in a pull request that says nothing about Django,
    and that is the moment this test fails: the wall is gone, so the entry that names it should
    go too. The mirror of this is `test_admin.py::test_the_sortable_admin_has_a_script_for_this
    _django`, which fails if Django is upgraded past the wall while it still stands.
    """
    ceiling = django_ceiling()
    if ceiling is None:
        pytest.skip("Django is no longer held below a ceiling, so there is nothing to justify")

    from django.contrib.staticfiles import finders

    script = f"adminsortable2/js/actions-{ceiling}.js"
    assert finders.find(script) is None, (
        f"django-admin-sortable2 now ships {script}, so nothing stops Django {ceiling} any more. "
        f"Remove the `ignore` entry for django from .github/dependabot.yml and let the upgrade through."
    )
