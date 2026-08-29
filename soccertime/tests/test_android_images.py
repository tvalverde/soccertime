"""Every image the applications draw must have something to draw when there is no image.

The API deliberately serves an image URL whether or not the file is behind it — `serializers.py`
says so, and says why: a client asking for a missing image gets a 404 from the web server, which
is a better answer than a 500 from here. That is the right decision, and it was paid for once
already, when 49 flag rows pointing at files that were gone returned 500 from `/competitions/`.

It leaves the client holding one obligation: a 404 must render as something. Coil draws nothing
at all for a request that fails, so an `AsyncImage` without `error` leaves a hole in a row that
has already reserved the space for the crest — and `fallback` is the same obligation for the URL
the API never sent. Neither is a compile error, neither is a crash, and neither shows up on a
developer machine, where the media directory is complete. It is only visible to somebody looking
at a screen fed by a production that has lost a file.

The second rule is what keeps the first one true. The two applications held byte-identical copies
of this composable, and the fix had to be written twice or written once; drawing images belongs
to `:core`, where there is one definition to give a missing state to.

Read as text rather than parsed, for the reason `test_android_materials.py` gives: a Kotlin
parser is not worth a dependency for this.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "android"

MODULES = ("core", "app-mobile", "app-tv")
IMAGE_PACKAGE = "coil3.compose"
DRAWS_IMAGES = "core"


def sources(module: str) -> list[Path]:
    return sorted((ANDROID / module / "src" / "main" / "kotlin").rglob("*.kt"))


def calls(text: str, name: str) -> list[str]:
    """Every call to `name`, from its opening bracket to the one that closes it.

    `AsyncImage` is matched on a word boundary so `SubcomposeAsyncImage` is a different
    function rather than a hit inside this one.
    """
    blocks = []
    for start in range(len(text)):
        if not text.startswith(name, start):
            continue
        before = text[start - 1] if start else " "
        if before.isalnum() or before == "_":
            continue
        opening = start + len(name)
        if opening >= len(text) or text[opening] != "(":
            continue
        depth = 0
        for end in range(opening, len(text)):
            if text[end] == "(":
                depth += 1
            elif text[end] == ")":
                depth -= 1
                if depth == 0:
                    blocks.append(text[start : end + 1])
                    break
    return blocks


def image_calls() -> list[tuple[Path, str]]:
    return [
        (path, block)
        for module in MODULES
        for path in sources(module)
        for block in calls(path.read_text(), "AsyncImage")
    ]


class TestTheScanFindsSomething:
    """Guards everything below: a scan matching nothing would assert nothing."""

    def test_the_modules_have_kotlin_sources(self):
        assert all(sources(module) for module in MODULES)

    def test_an_image_is_drawn_somewhere(self):
        assert image_calls(), "no AsyncImage call found — has it been renamed?"


def test_every_image_has_something_to_draw_when_there_is_none():
    """`error` covers the file that is gone, `fallback` the URL that was never sent."""
    offenders = [
        f"{path.relative_to(ANDROID)}: AsyncImage without {' and '.join(missing)}"
        for path, block in image_calls()
        if (missing := [slot for slot in ("error", "fallback") if f"{slot} =" not in block])
    ]
    assert not offenders, "\n".join(offenders)


def test_only_the_shared_module_draws_images():
    """One definition to give a missing state to, rather than one per application."""
    offenders = [
        f"{path.relative_to(ANDROID)}: {line.strip()}"
        for module in MODULES
        if module != DRAWS_IMAGES
        for path in sources(module)
        for line in path.read_text().splitlines()
        if line.startswith(f"import {IMAGE_PACKAGE}")
    ]
    assert not offenders, "\n".join(offenders)
