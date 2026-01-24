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
from django.urls import path
from django.views.generic.base import RedirectView

from soccertime.views import (
    agenda,
    channel_events,
    channels,
    competition_events,
    competitions,
    favorites,
    sport_events,
    team_events,
)

urlpatterns = []

if os.environ.get("DJANGO_ADMIN_ENABLED", "").lower() == "true":
    urlpatterns.append(path("admin/", admin.site.urls))

urlpatterns += [
    path("", RedirectView.as_view(url="favorites/")),
    path("favorites/", favorites, name="favorites"),
    path("events/", RedirectView.as_view(url="../favorites/")),
    path("agenda/", agenda, name="agenda"),
    path("events/team/<str:team>/", team_events, name="team-events"),
    path("events/channel/<str:channel>/", channel_events, name="channel-events"),
    path("events/sport/<str:sport>/", sport_events, name="sport-events"),
    path("events/competition/<str:competition>/", competition_events, name="competition-events"),
    path("channels/", channels, name="channels"),
    path("competitions/", competitions, name="competitions"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
