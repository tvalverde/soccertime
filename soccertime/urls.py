"""
URL configuration for soccertime project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, path
from django.views.generic.base import RedirectView, TemplateView

from soccertime.views import (
    agenda,
    channel_events,
    channels,
    competition_events,
    competitions,
    favorites,
    healthz,
    sport_events,
    team_events,
    toggle_favorite_competition,
    toggle_favorite_team,
)


def admin_is_enabled() -> bool:
    """Whether the admin should be routed at all.

    This is a security control rather than a convenience: production runs with the flag
    off, so `/admin/` resolves to nothing and there is no login form to guess against.
    Only the exact string `true` enables it, so a typo fails closed.
    """
    return os.environ.get("DJANGO_ADMIN_ENABLED", "").lower() == "true"


# Kept apart from the rest so a test can compose a URLconf that routes the admin without
# depending on the environment the suite happens to run in. The container sets the flag
# to `true`, which is what let the admin tests pass while production had it off.
admin_urlpatterns: list[URLPattern | URLResolver] = [path("admin/", admin.site.urls)]

site_urlpatterns: list[URLPattern | URLResolver] = [
    path("healthz/", healthz, name="healthz"),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain"), name="robots-txt"),
    path("", RedirectView.as_view(url="favorites/")),
    path("favorites/", favorites, name="favorites"),
    path("events/", RedirectView.as_view(url="../favorites/")),
    path("agenda/", agenda, name="agenda"),
    path("events/team/<int:team>/", team_events, name="team-events"),
    path("events/channel/<int:channel>/", channel_events, name="channel-events"),
    path("events/sport/<int:sport>/", sport_events, name="sport-events"),
    path("events/competition/<int:competition>/", competition_events, name="competition-events"),
    path("channels/", channels, name="channels"),
    path("competitions/", competitions, name="competitions"),
    # The only writes the site accepts without a login, under a prefix of their own so the
    # proxy can rate-limit exactly these and nothing else. `/favorites/` is the landing page
    # and must not be caught by that rule, which is why this is not under it.
    path("favorite/toggle/team/<int:team>/", toggle_favorite_team, name="toggle-favorite-team"),
    path(
        "favorite/toggle/competition/<int:competition>/",
        toggle_favorite_competition,
        name="toggle-favorite-competition",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = []

if admin_is_enabled():
    urlpatterns += admin_urlpatterns

urlpatterns += site_urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
