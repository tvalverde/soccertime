"""Whether the admin is routed at all is a security control, so it is pinned here.

Production runs with `DJANGO_ADMIN_ENABLED` off, which is what makes `/soccertime/admin/`
answer 404 rather than presenting a login form to the internet with nothing slowing down
a guess. Nothing tested that: the flag was read at import time and every test inherited
whatever the container carried, which is the same assumption that let the admin tests
pass while production had the flag off.

These reload the URLconf under a chosen environment instead, so they assert what the flag
does rather than what the environment happens to be.
"""

import importlib
import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from django.urls import clear_url_caches

import soccertime.urls

PUBLIC_ROUTES = {"healthz/", "favorites/", "agenda/", "channels/", "competitions/"}


@contextmanager
def routes_with_flag(value: str | None) -> Iterator[set[str]]:
    """Reload the URLconf with the flag set to `value`, yielding the routes it produced."""
    previous = os.environ.get("DJANGO_ADMIN_ENABLED")
    if value is None:
        os.environ.pop("DJANGO_ADMIN_ENABLED", None)
    else:
        os.environ["DJANGO_ADMIN_ENABLED"] = value
    try:
        yield {str(pattern.pattern) for pattern in importlib.reload(soccertime.urls).urlpatterns}
    finally:
        if previous is None:
            os.environ.pop("DJANGO_ADMIN_ENABLED", None)
        else:
            os.environ["DJANGO_ADMIN_ENABLED"] = previous
        importlib.reload(soccertime.urls)
        clear_url_caches()


class TestTheAdminIsRoutedOnlyOnAnExplicitTrue:
    """A typo, a blank or a truthy-looking value must all fail closed."""

    @pytest.mark.parametrize("value", ["false", "False", "", "0", "1", "yes", "on", "true ", "truthy"])
    def test_anything_that_is_not_true_leaves_it_unrouted(self, value):
        with routes_with_flag(value) as routes:
            assert "admin/" not in routes

    def test_an_absent_variable_leaves_it_unrouted(self):
        """How the container behaves if `.env.production` is missing an entry."""
        with routes_with_flag(None) as routes:
            assert "admin/" not in routes

    @pytest.mark.parametrize("value", ["true", "True", "TRUE"])
    def test_true_routes_it_whatever_the_casing(self, value):
        with routes_with_flag(value) as routes:
            assert "admin/" in routes


def test_turning_the_admin_off_takes_nothing_else_with_it():
    """The public site must be identical either way; only the admin route may differ."""
    with routes_with_flag("false") as disabled:
        without_admin = disabled
    with routes_with_flag("true") as enabled:
        with_admin = enabled

    assert with_admin - without_admin == {"admin/"}
    assert without_admin - with_admin == set()
    assert PUBLIC_ROUTES <= without_admin
