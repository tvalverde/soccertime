"""A URLconf that always routes the admin, whatever the environment says.

`soccertime.urls` registers the admin only when `DJANGO_ADMIN_ENABLED` is `true`, and
production runs with it off. Tests that reverse an `admin:` URL were therefore passing
on an accident: the image bakes the flag as `true`, so the suite inherited a routed
admin from its container rather than from anything it asked for. Running them with the
flag production actually uses failed with `NoReverseMatch`.

Pointing those tests here with `pytest.mark.urls` states the dependency instead of
inheriting it, and leaves them free to keep testing the admin while the flag that
governs the real site is free to change.
"""

from soccertime.urls import admin_urlpatterns, site_urlpatterns

urlpatterns = [*admin_urlpatterns, *site_urlpatterns]
