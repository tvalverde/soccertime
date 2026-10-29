"""Every target the Makefile defines is declared phony, and nothing else is.

None of these targets produces a file of its own name, so a file that happened to carry one —
a `test` directory, a stray `lint` — would make Make call the target up to date and run
nothing, silently. `.PHONY` is what prevents that, and it is one long line that is easy to get
wrong without anything complaining: two names once ran together as
`remote-error-checkremote-smoke-test`, which declared a target that does not exist and left
both real ones unprotected.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"


def declared_phony() -> set[str]:
    match = re.search(r"(?m)^\.PHONY:(.*)$", MAKEFILE.read_text())
    assert match, "the Makefile declares no .PHONY line"
    return set(match.group(1).split())


def defined_targets() -> set[str]:
    return set(re.findall(r"(?m)^([A-Za-z0-9_-]+):(?!=)", MAKEFILE.read_text()))


def test_the_makefile_is_readable():
    """Guards the assertions below: a parser reading nothing would assert nothing."""
    assert declared_phony()
    assert defined_targets()


def test_every_phony_name_is_a_target():
    assert declared_phony() - defined_targets() == set()


def test_every_target_is_phony():
    assert defined_targets() - declared_phony() == set()
