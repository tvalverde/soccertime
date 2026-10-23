"""The site runs a Django that carries the security release of 2026-10-06.

Django 6.0.9 fixed CVE-2026-84429: `parse_header_parameters()` took quadratic time on a quoted
parameter full of separators, and it is reached through `HttpRequest.accepts()` and the parsing
of `Content-Type` — by any request, unauthenticated, to any page. 6.0.8 was pinned until then,
and nothing would have said so: the pin is exact, so the resolver never moves it on its own.

Asking the installed package rather than reading `requirements.txt` makes this hold for what
actually runs: CI installs from the file, and so does the image.
"""

import django

FIRST_PATCHED = (6, 0, 9)


def test_the_installed_django_carries_the_october_security_release():
    assert django.VERSION[:3] >= FIRST_PATCHED, django.get_version()
