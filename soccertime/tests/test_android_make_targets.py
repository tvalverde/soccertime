"""The Android targets build against the developer's own Gradle cache, and say so if not.

`~/.gradle` is three gigabytes shared by every Gradle project on the machine, and sharing it
is the point: a build that resolves its own copy resolves its own dependency tree, which can
differ from the one the developer sees. "It compiles for me" quietly stopping to mean "it
compiles for you" is among the slowest failures to diagnose, and the pinned
`kotlin-gradle-plugin` in the root buildscript makes two independent resolutions less alike
than they look.

This is guarded rather than written down because it was already written down as an intention
and still went wrong. A tool sandbox refused a write to `~/.gradle`; the answer was to point
`GRADLE_USER_HOME` at a temporary directory; and that answer outlived the sandbox that caused
it, so every later build in the session re-downloaded a gigabyte and a half and started a
second daemon beside the one already warm. Nothing complained, because nothing was watching.

The guard is a prerequisite of every `android-*` target that runs Gradle, so improvising an
environment and calling `./gradlew` by hand is the only way past it — which is the same reason
this project keeps its production operations in the Makefile rather than in ad-hoc commands.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"

GUARD = "check-gradle-home"

# Every target that hands work to Gradle. `android-install-*` drive adb and the Gradle install
# tasks through the same wrapper, so they are covered by the ones they depend on being built.
GRADLE_TARGETS = ("android-build", "android-test", "android-lint", "android-clean", "android-release")


def makefile() -> str:
    """The Makefile with its comments dropped, so a comment cannot satisfy an assertion."""
    text = MAKEFILE.read_text()
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_the_makefile_is_readable():
    """Guards everything below: a file that scanned as empty would assert nothing."""
    assert "android-build" in makefile()


def test_the_guard_exists():
    assert re.search(rf"(?m)^{GUARD}:", makefile()), f"{GUARD} is gone; the targets below guard nothing"


def test_the_guard_is_declared_phony():
    """Without this, a file of that name in the tree would satisfy make and never run."""
    phony = re.search(r"(?m)^\.PHONY:(.*)$", makefile())
    assert phony and GUARD in phony.group(1)


def test_the_guard_rejects_a_home_outside_the_user_s():
    """The check itself: a prefix comparison against `$HOME`, and a non-zero exit."""
    body = makefile()
    assert "GRADLE_USER_HOME#" in body, "the guard no longer compares the value against $HOME"
    assert "exit 1" in body.split(f"{GUARD}:")[1][:900], "the guard warns without failing"


def test_every_gradle_target_waits_for_it():
    """A target that forgets the prerequisite is a way back to the cache that caused this."""
    body = makefile()
    unguarded = [target for target in GRADLE_TARGETS if not re.search(rf"(?m)^{target}:.*\b{GUARD}\b", body)]
    assert not unguarded, f"these run Gradle without checking where its cache points: {', '.join(unguarded)}"
