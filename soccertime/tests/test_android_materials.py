"""Neither application may draw with the other's Material.

There are two Materials in this project and they are not interchangeable.
`androidx.compose.material3` builds controls a finger operates; `androidx.tv.material3`
builds controls a remote operates, and the difference is whether a thing can be reached
at all. A `Text` is harmless either way, but a `Button` or a `Surface` from the wrong one
is a control the D-pad walks straight past.

Both export types of the same name, so an import completed by an editor reads as correct, and
the mistake is only found by somebody sitting in front of a television unable to reach a
button.

What stands between here and there is the classpath, and it holds only while nobody widens it.
`androidx.tv:tv-material:1.1.0` does **not** depend on `androidx.compose.material3` — checked in
its Gradle metadata, where the only material it brings is `material-icons-core` — so today the
compiler would refuse the wrong import in either application, and the import checks below are
the belt to the declarations' braces. That is a statement about one version of one library,
which is exactly why it is not left to hold on its own: an earlier version of this file recorded
the opposite as settled fact.

`:core` holds neither, and that is the stronger statement: the view models there are shared by
both applications, so anything of the toolkit in them would decide for both. The fonts and the
icons in `core/ui` are Compose but not Material, which is exactly the line this draws.

The rule is checked twice, at the window and at the door. Reading imports catches the line
that draws with the wrong toolkit; reading the build files catches the dependency that lets
such a line compile in the first place. Without the second, `api(libs.compose.material3)`
could sit in `:core` indefinitely, green, waiting for the first import to arrive.

What is deliberately *not* checked here is that a module declares every artifact it imports
from. Gradle does not hand a module its consumers' dependencies and the Kotlin compiler fails
on a package that is not on the classpath, so `:core` cannot lean on what the applications
carry: that lesson cost a `foundation-layout` declaration on 2026-08-29 and the build enforces
it without help. A package-to-artifact table here would duplicate knowledge that already lives
in the build files and drifts with every upgrade — `foundation` publishes `foundation-layout`
to its runtime classpath but not its compile one, which is true of Compose 1.12 and is nobody's
promise about 1.13.

Read as text rather than parsed: an import is a line, and a Kotlin parser is not worth a
dependency for one.
"""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "android"

PHONE_MATERIAL = "androidx.compose.material3"
TV_MATERIAL = "androidx.tv.material3"

# The Maven coordinates behind each of the two, as the catalog spells them.
PHONE_MATERIAL_MODULE = "androidx.compose.material3:material3"
TV_MATERIAL_MODULE = "androidx.tv:tv-material"

# Which Material each module may import, and which it may not.
MODULES = {
    "app-mobile": (PHONE_MATERIAL, TV_MATERIAL),
    "app-tv": (TV_MATERIAL, PHONE_MATERIAL),
}

# The same pairing at the dependency level: what each build file may ask for, and may not.
DECLARATIONS = {
    "app-mobile": (PHONE_MATERIAL_MODULE, TV_MATERIAL_MODULE),
    "app-tv": (TV_MATERIAL_MODULE, PHONE_MATERIAL_MODULE),
}

# `libs.compose.material3` in a build file is the alias `compose-material3` in the catalog.
# `libs.plugins.…`, `libs.versions.…` and `libs.bundles.…` address other tables: a bundle is a
# list of aliases and would need resolving through its own, so it is read separately below.
CATALOG_REFERENCE = re.compile(r"\blibs\.((?!plugins\.|versions\.|bundles\.)[A-Za-z0-9.]+)")


def sources(module: str) -> list[Path]:
    return sorted((ANDROID / module / "src" / "main" / "kotlin").rglob("*.kt"))


def imports(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.startswith("import ")]


def catalog() -> dict[str, str]:
    """Every library the version catalog names, as alias to Maven coordinates."""
    with (ANDROID / "gradle" / "libs.versions.toml").open("rb") as handle:
        parsed = tomllib.load(handle)
    return {alias: entry["module"] for alias, entry in parsed["libraries"].items() if "module" in entry}


def build_file(module: str) -> str:
    """The build file with its comments dropped, so a comment cannot satisfy an assertion.

    The same reason `test_android_release.py` drops them: a line that is commented out asks
    for nothing, and a line that merely names a library in prose forbids nothing.
    """
    text = (ANDROID / module / "build.gradle.kts").read_text()
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def declared_modules(module: str) -> set[str]:
    """The coordinates a module's build file asks for, however it asks for them.

    Catalog references are resolved rather than matched by name, because the alias says
    nothing on its own: it is `libs.androidx.tv.material` that carries `androidx.tv:tv-material`,
    and a rename of either side must not quietly turn this check off.

    Coordinates written out as a string are read too. The catalog is the convention here and
    every dependency follows it, but `api("androidx.compose.material3:material3")` is valid
    Gradle — the BOM would even supply the version — and a check that only knew about aliases
    would wave it through.
    """
    libraries = catalog()
    text = build_file(module)
    referenced = {
        libraries[alias]
        for reference in CATALOG_REFERENCE.findall(text)
        if (alias := reference.replace(".", "-")) in libraries
    }
    spelled_out = {coordinates for coordinates in libraries.values() if f'"{coordinates}' in text}
    return referenced | spelled_out


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


class TestTheBuildFilesAgreeWithTheSources:
    """The door, where the import test is the window.

    An import can only compile if something put the library on the classpath, so the
    declaration is the earlier and quieter mistake: it passes every check here until the
    first import arrives, which may be months and a different pair of hands later.
    """

    def test_the_catalog_resolves(self):
        """Guards the two below: coordinates nobody can resolve would assert nothing."""
        assert catalog()

    @pytest.mark.parametrize("module", sorted(DECLARATIONS))
    def test_each_application_asks_for_the_material_it_draws_with(self, module):
        allowed, _ = DECLARATIONS[module]
        assert allowed in declared_modules(module), f"{module} does not declare {allowed}"

    @pytest.mark.parametrize("module", sorted(DECLARATIONS))
    def test_neither_application_asks_for_the_other_s(self, module):
        _, forbidden = DECLARATIONS[module]
        assert forbidden not in declared_modules(module), (
            f"{module} declares {forbidden}, which puts the wrong controls one import away"
        )

    def test_the_shared_module_asks_for_neither(self):
        """`:core` is shared, so a Material on its classpath is a Material for both."""
        declared = declared_modules("core")
        offenders = sorted({PHONE_MATERIAL_MODULE, TV_MATERIAL_MODULE} & declared)

        assert not offenders, f"core/build.gradle.kts declares {', '.join(offenders)}"
