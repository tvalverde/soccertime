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


def ceiling_of(dependency: str) -> str | None:
    """The version from which `dependabot.yml` refuses to offer `dependency`, if it does.

    Read from the configuration rather than written down a second time here, so the two
    cannot say different things.
    """
    ignored = re.compile(rf'dependency-name:\s*"{re.escape(dependency)}"\s*\n\s*versions:\s*\[">=([\d.]+)"\]')
    found = ignored.search(CONFIG.read_text())
    return found.group(1) if found else None


def django_ceiling() -> str | None:
    return ceiling_of("django")


def python_ceiling() -> str | None:
    return ceiling_of("python")


def pythons_django_supports() -> set[str]:
    """The interpreters the installed Django declares, from its own package metadata."""
    from importlib.metadata import metadata

    prefix = "Programming Language :: Python :: "
    classifiers = metadata("Django").get_all("Classifier") or []
    return {c.removeprefix(prefix) for c in classifiers if re.fullmatch(rf"{re.escape(prefix)}\d+\.\d+", c)}


def test_django_declares_the_pythons_it_supports():
    """Guards the two tests below: an empty set would make both pass for the wrong reason."""
    assert pythons_django_supports()


def test_the_base_image_runs_a_python_django_supports():
    """The interpreter in the `Dockerfile` is one the pinned Django says it runs on.

    Python 3.15 arrived while Django was held at 6.0, whose releases stop at 3.14; the base
    image bump was proposed anyway and only failed CI on an unrelated guard. Bumping the
    image by hand would not even have done that.
    """
    from soccertime.tests.test_published_image import base_image_python_version

    assert base_image_python_version() in pythons_django_supports()


def test_the_python_ceiling_is_still_a_wall():
    """Says when the reason for holding the base image's Python back has stopped being true.

    `dependabot.yml` ignores the Python the pinned Django does not declare. The day a Django
    release that declares it lands in `requirements.txt` — a 6.0 patch adding it, or the 6.1
    line once `test_the_django_ceiling_is_still_a_wall` lets it through — this fails, and the
    entry should go so the image upgrade is proposed again.
    """
    ceiling = python_ceiling()
    if ceiling is None:
        pytest.skip("Python is no longer held below a ceiling, so there is nothing to justify")

    assert ceiling not in pythons_django_supports(), (
        f"The pinned Django now declares Python {ceiling}, so nothing stops the base image any more. "
        f"Remove the `ignore` entry for python from .github/dependabot.yml and let the upgrade through."
    )


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
