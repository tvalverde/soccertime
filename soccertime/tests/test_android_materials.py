"""Neither application may draw with the other's Material.

There are two Materials in this project and they are not interchangeable.
`androidx.compose.material3` builds controls a finger operates; `androidx.tv.material3`
builds controls a remote operates, and the difference is whether a thing can be reached
at all. A `Text` is harmless either way, but a `Button` or a `Surface` from the wrong one
is a control the D-pad walks straight past.

Nothing catches that. Both libraries are on the television's compile classpath — `tv-material`
depends on `compose.material3` itself, so it cannot be excluded — and both export types of the
same name, so an import completed by an editor compiles, builds, ships, and is only found by
somebody sitting in front of a television unable to reach a button.

`:core` holds neither, and that is the stronger statement: the view models there are shared by
both applications, so anything of the toolkit in them would decide for both. The fonts and the
icons in `core/ui` are Compose but not Material, which is exactly the line this draws.

Read as text rather than parsed: an import is a line, and a Kotlin parser is not worth a
dependency for one.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "android"

PHONE_MATERIAL = "androidx.compose.material3"
TV_MATERIAL = "androidx.tv.material3"

# Which Material each module may import, and which it may not.
MODULES = {
    "app-mobile": (PHONE_MATERIAL, TV_MATERIAL),
    "app-tv": (TV_MATERIAL, PHONE_MATERIAL),
}


def sources(module: str) -> list[Path]:
    return sorted((ANDROID / module / "src" / "main" / "kotlin").rglob("*.kt"))


def imports(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.startswith("import ")]


class TestTheSourcesAreReadable:
    """Guards every assertion below: a scan finding no files would assert nothing."""

    @pytest.mark.parametrize("module", sorted(MODULES))
    def test_the_module_has_kotlin_sources(self, module):
        assert sources(module)

    def test_the_shared_module_has_kotlin_sources(self):
        assert sorted((ANDROID / "core" / "src" / "main" / "kotlin").rglob("*.kt"))


class TestEachApplicationDrawsWithItsOwn:
    @pytest.mark.parametrize("module", sorted(MODULES))
    def test_it_imports_the_material_it_is_meant_to(self, module):
        allowed, _ = MODULES[module]
        used = [path for path in sources(module) if any(line.startswith(f"import {allowed}") for line in imports(path))]
        assert used, f"{module} imports nothing from {allowed}"

    @pytest.mark.parametrize("module", sorted(MODULES))
    def test_it_imports_nothing_from_the_other(self, module):
        _, forbidden = MODULES[module]
        offenders = [
            f"{path.relative_to(ANDROID)}: {line}"
            for path in sources(module)
            for line in imports(path)
            if line.startswith(f"import {forbidden}")
        ]
        assert not offenders, "\n".join(offenders)


def test_the_shared_module_holds_neither():
    """A control chosen in `:core` would be chosen for both applications at once."""
    offenders = [
        f"{path.relative_to(ANDROID)}: {line}"
        for path in (ANDROID / "core" / "src" / "main" / "kotlin").rglob("*.kt")
        for line in imports(path)
        if line.startswith((f"import {PHONE_MATERIAL}", f"import {TV_MATERIAL}"))
    ]
    assert not offenders, "\n".join(offenders)
