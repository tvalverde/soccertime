"""The site runs a Pillow and a Django REST framework that carry their October 2026 fixes.

Pillow 13.0.0 (2026-10-15) ships a patched OpenJPEG for GHSA-78g4-xqwv-q3g8, a heap overflow
write reachable from `Image.open(...).load()` that a patched host does not fix, because every
wheel since 11.1.0 bundles its own copy. The same release closes some forty more, among them
a critical JPEG decoder overflow. `images.py` no longer offers scraped bytes to any decoder
outside its allowlist, which keeps that one away whatever the version; the rest are why the
version matters too.

Django REST framework 3.18.2 fixed GHSA-xw6w-gcfp-cf8m: `TokenProxy.delete()` reported success
and revoked nothing. This site does not install `rest_framework.authtoken`, so it is guarded
here for the day it does, not because it is exposed today.

Both pins are exact, so nothing would move them on its own. Asking the installed packages
rather than reading `requirements.txt` makes this hold for what actually runs.
"""

from importlib.metadata import version

import pytest


def release(package: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version(package).split(".")[:3])


@pytest.mark.parametrize(
    ("package", "first_patched"),
    [("pillow", (13, 0, 0)), ("djangorestframework", (3, 18, 2))],
)
def test_the_installed_package_carries_its_october_security_release(package, first_patched):
    assert release(package) >= first_patched, version(package)
