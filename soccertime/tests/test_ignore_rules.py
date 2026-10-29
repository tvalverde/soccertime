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
not there on a fresh clone.

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
# so. Unanchored they also match a `media/` or `db/` directory anywhere below the root.
ROOT_ONLY = ("media", "db")


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
