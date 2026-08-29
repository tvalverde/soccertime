"""Nothing the environment leaves lying around is versioned by accident.

Run through a tool sandbox, this working copy appears to contain twelve untracked entries it
does not have: `.bashrc`, `.zshrc`, `.gitconfig`, `.gitmodules`, `.mcp.json`, `.idea`,
`.vscode` and the rest. Eleven of them do not exist on disk at all — they are bind mounts the
sandbox lays over the working directory, and they vanish with it. `git status` cannot tell
them from real files, so `git add -A` sweeps them in and the repository grows somebody's
personal shell configuration.

`CLAUDE.md` says to stage explicit paths, and that has held for more than 250 commits. But a
rule that lives in prose is a rule somebody has to have read, and this project has already
paid for one of those: the changelog went unmaintained for exactly that reason. This is the
same rule with a machine behind it.

Written as an allowlist rather than a list of the twelve known intruders, because the
interesting failure is the artefact nobody has seen yet — a new tool, a new sandbox, a new
editor directory. What the root of this repository versions is small and slow-moving; anything
else appearing there is a question rather than an answer.

The enforcement point is CI, which runs pytest on a real checkout. `make test` runs inside the
application image, which ships no `git` — so this skips there, and says so.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Every dotfile and dot-directory this repository tracks at its root. Add to it deliberately:
# a new entry here is a decision that something starting with a dot belongs in the project.
VERSIONED_ROOT_DOTFILES = frozenset(
    {
        ".antigravityignore",
        ".claudeignore",
        ".docker",
        ".dockerignore",
        ".env.example",
        ".env.production.local.example",
        ".geminiignore",
        ".gitattributes",
        ".github",
        ".gitignore",
    }
)


def tracked_paths() -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("no git and no checkout here; CI runs this on a real one")
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [path for path in listing.stdout.split("\0") if path]


def test_the_listing_is_readable():
    """Guards the test below: a listing that came back empty would assert nothing at all."""
    assert len(tracked_paths()) > 100


def test_no_artefact_of_the_environment_is_tracked():
    intruders = sorted(
        {path.split("/")[0] for path in tracked_paths() if path.startswith(".")} - VERSIONED_ROOT_DOTFILES
    )

    assert not intruders, (
        f"{', '.join(intruders)} is tracked at the root of this repository. If the sandbox put "
        f"it there, remove it with `git rm --cached` and stage explicit paths rather than "
        f"`git add -A`. If it is genuinely part of the project, add it to "
        f"VERSIONED_ROOT_DOTFILES and say so in the commit."
    )
