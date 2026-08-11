"""What each dependency list is for, and that neither drifts into the other.

The production image used to install pytest, ruff, mypy and django-stubs, because one file
described both environments. They are split now, and the split invites two mistakes that
nothing else would catch.

The first is an unpinned line. `lxml` sat at the bottom of the old file with no version at
all, so a rebuild could silently change the HTML parser the scraper depends on, with no
record of what had been tested. Asserting every line is pinned is the general form of that
finding rather than a fix for the one line.

The second is putting `lxml` in the development list, which is where its old position in
the file suggested it belonged. It is a production dependency: `futbolenlatv.py` asks
BeautifulSoup for it by name. Get that wrong and the site carries on serving perfectly —
only the next scrape fails.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ROOT / "requirements.txt"
DEVELOPMENT = ROOT / "requirements-dev.txt"

TOOLCHAIN = {"pytest", "pytest-django", "pytest-cov", "ruff", "mypy", "django-stubs", "types-requests"}


def requirements(path):
    """The lines that declare a dependency, comments and blanks dropped."""
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def names(path):
    return {re.split(r"[=<>!~\[]", line)[0].strip().lower() for line in requirements(path)}


@pytest.mark.parametrize("path", [PRODUCTION, DEVELOPMENT], ids=["production", "development"])
def test_every_dependency_is_pinned(path):
    """An unpinned line lets a rebuild change what runs, with nothing recording what did."""
    unpinned = [line for line in requirements(path) if "==" not in line]

    assert unpinned == []


def test_the_toolchain_lives_only_in_the_development_list():
    assert TOOLCHAIN <= names(DEVELOPMENT)
    assert not (TOOLCHAIN & names(PRODUCTION))


def test_lxml_is_a_production_dependency():
    """The scraper parses with it by name; the site would keep serving while scrapes failed."""
    assert "lxml" in names(PRODUCTION)
    assert "lxml" not in names(DEVELOPMENT)


def test_the_application_dependencies_are_all_there():
    """Guards the test itself: a parser that read nothing would assert nothing."""
    assert {"django", "requests", "beautifulsoup4", "pillow", "uvicorn", "whitenoise"} <= names(PRODUCTION)
