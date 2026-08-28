"""What `.gitignore` and `.dockerignore` have to keep in and keep out.

Both files are read by something other than a person, and both fail silently. A pattern
that matches too much drops a source file out of the repository with no error anywhere;
a pattern that matches too little carries build output into the image.

The entries that matter here are the bare ones. A `.gitignore` line with no slash is
matched against *every* path segment at every depth, so `media` and `db` — written for
the Django media root and the directory the SQLite file lives in — also hide any
directory of those names anywhere else in the tree. Nothing in the Python project is
called either, which is why it never showed; a second project in this repository is
exactly the thing that would make it show, and it would show as a file that is simply
not there on a fresh clone. `build/` is deliberately left bare: there the depth-matching
is the point, because it is what covers every module's Gradle output.

Asserted against the text rather than against `git check-ignore`, which would have been
the better question to ask: the development container carries neither `git` nor a `.git`
directory, so every such assertion skipped there and only ever ran on the CI runner — a
test nobody sees fail while writing the change is not one that protects it.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GITIGNORE = ROOT / ".gitignore"
DOCKERIGNORE = ROOT / ".dockerignore"

# Written for a directory at the repository root and for nothing else, so each has to say
# so. Unanchored they also match `android/.../media/` and `android/.../db/`.
ROOT_ONLY = ("media", "db")

# Gradle output and per-machine state. None of it belongs in a commit, and `android/` is
# where all of it appears.
ANDROID_PATTERNS = (
    "android/.gradle/",
    "android/local.properties",
    "android/**/build/",
    "*.apk",
    "*.aab",
    "*.jks",
    "*.keystore",
)


def patterns(path: Path) -> list[str]:
    return [
        line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]


def test_the_ignore_files_are_readable():
    """Guards the assertions below: a parser reading nothing would assert nothing."""
    assert patterns(GITIGNORE)
    assert patterns(DOCKERIGNORE)


@pytest.mark.parametrize("name", ROOT_ONLY)
def test_the_root_only_entries_are_anchored(name):
    found = patterns(GITIGNORE)
    assert name not in found, f"bare `{name}` also hides every `{name}` directory below the root"
    assert f"/{name}/" in found


@pytest.mark.parametrize("pattern", ANDROID_PATTERNS)
def test_the_android_build_output_is_ignored(pattern):
    assert pattern in patterns(GITIGNORE)


def test_the_docker_build_does_not_carry_the_android_project():
    """`COPY . .` takes everything the ignore file does not refuse, and this is none of it."""
    assert "android/" in patterns(DOCKERIGNORE)
