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
