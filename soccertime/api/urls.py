"""Where the API is mounted.

Under a version from the first day, because the alternative is discovering later that a
client depends on a shape and having nowhere to put the new one. `/api/` redirects to the
current version so a caller who guessed the prefix lands somewhere useful.
"""

from django.urls import URLPattern, URLResolver, include, path
from django.views.generic.base import RedirectView
from drf_spectacular.views import SpectacularAPIView
from rest_framework import routers

from soccertime.api.views import (
    ApiDocsView,
    ApiRootView,
    ChannelLinkSourceViewSet,
    ChannelLinkViewSet,
    ChannelViewSet,
    CompetitionViewSet,
    EventViewSet,
    FavoriteViewSet,
    FlagViewSet,
    SportViewSet,
    TeamViewSet,
)
from soccertime.views import cached_page

router = routers.DefaultRouter()
router.APIRootView = ApiRootView
router.register("sports", SportViewSet, basename="sport")
router.register("competitions", CompetitionViewSet, basename="competition")
router.register("teams", TeamViewSet, basename="team")
router.register("flags", FlagViewSet, basename="flag")
router.register("channels", ChannelViewSet, basename="channel")
router.register("channel-links", ChannelLinkViewSet, basename="channel-link")
router.register("channel-link-sources", ChannelLinkSourceViewSet, basename="channel-link-source")
router.register("events", EventViewSet, basename="event")
router.register("favorites", FavoriteViewSet, basename="favorite")

# Both are cached the way the pages are, because both are the same bytes for everybody and
# neither depends on the request. The schema is introspected from every viewset and
# serializer on each GET — cheap today at ~45 ms, but it is pure CPU on the one core the
# container has, and it is the one endpoint whose answer only changes when a deploy does.
version_urlpatterns: list[URLPattern | URLResolver] = [
    path("schema/", cached_page(SpectacularAPIView.as_view()), name="api-schema"),
    path("docs/", cached_page(ApiDocsView.as_view()), name="api-docs"),
    path("", include(router.urls)),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("v1/", include(version_urlpatterns)),
    path("", RedirectView.as_view(pattern_name="api-root", permanent=False)),
]
