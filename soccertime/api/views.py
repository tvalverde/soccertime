"""The endpoints, one per table the site reads from.

Every viewset here reads and nothing writes. The site's only write is the favourites
cookie, which belongs to a browser and is signed for it; there is nothing an API caller
could hold that would authorise one, so offering a write would mean either an anonymous
one or an authentication system for a private site that has none.

The querysets are built per request rather than declared as class attributes, because two
of them ask what "today" is. A class attribute is evaluated when the module is imported,
so the container would keep answering with the day it was started — which is a week ago
by the time anybody notices.
"""

from typing import Any, ClassVar

from django.db.models import Count, IntegerField, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce
from django.utils.timezone import localtime
from django.views.generic import TemplateView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import routers, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.reverse import reverse

from soccertime.api import filtering
from soccertime.api.filtering import QueryFilter
from soccertime.api.serializers import (
    ChannelLinkSerializer,
    ChannelLinkSourceSerializer,
    ChannelSerializer,
    CompetitionDetailSerializer,
    EventSerializer,
    FavoriteSerializer,
    FlagSerializer,
    SportSerializer,
    TeamSerializer,
)
from soccertime.models import (
    ALLOWED_LINK_SCHEMES,
    Channel,
    ChannelLink,
    ChannelLinkSource,
    Competition,
    Event,
    Favorite,
    Flag,
    Sport,
    Team,
    start_of_today,
)

CHRONOLOGICAL = ("date", "competition__sport__order", "competition__name")
REVERSE_CHRONOLOGICAL = ("-date", "competition__sport__order", "competition__name")

WITH_A_CREST = ~(Q(crest__isnull=True) | Q(crest=""))


class ReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """A collection that can be listed and read, and nothing else.

    `query_filters` is applied by `QueryFilterBackend`, which also hands it to the schema
    generator, so a filter cannot exist without being documented.
    """

    query_filters: ClassVar[tuple[QueryFilter, ...]] = ()


class SportViewSet(ReadOnlyViewSet):
    """The sports events are grouped under, in the order the site lists them."""

    queryset = Sport.objects.all()
    serializer_class = SportSerializer
    query_filters = (
        filtering.switch(
            "with_events",
            "Only sports with at least one event from the start of today onwards.",
            lambda queryset: queryset.filter(pk__in=Sport.objects.with_events()),
        ),
        filtering.free_text("Case-insensitive match on the name.", "name"),
    )


class CompetitionViewSet(ReadOnlyViewSet):
    """The competitions of every sport, with how many events each still has to come."""

    queryset = Competition.objects.all()
    serializer_class = CompetitionDetailSerializer
    query_filters = (
        filtering.identifier("sport", "Only competitions of this sport.", "sport__pk"),
        filtering.switch(
            "has_upcoming_events",
            "Only competitions with an event from the start of today onwards.",
            lambda queryset: queryset.filter(upcoming_event_count__gt=0),
        ),
        filtering.switch(
            "favorite",
            "Only competitions on the owner's curated list.",
            lambda queryset: queryset.filter(favorite__isnull=False).distinct(),
        ),
        filtering.free_text("Case-insensitive match on the name.", "name"),
    )

    def get_queryset(self) -> QuerySet[Competition]:
        """Counted with a subquery rather than an aggregate over a join.

        `annotate(Count("events", filter=...))` gives the right number until something
        filters on `events` as well — the filter opens a second join, the rows multiply and
        the count silently inflates. It also lets `has_upcoming_events` reuse the number
        already computed instead of joining again.
        """
        upcoming = (
            Event.objects.filter(competition=OuterRef("pk"), date__gte=start_of_today())
            .values("competition")
            .annotate(total=Count("pk"))
            .values("total")
        )
        return (
            Competition.objects.select_related("sport", "flag")
            .prefetch_related("favorite")
            .annotate(upcoming_event_count=Coalesce(Subquery(upcoming, output_field=IntegerField()), 0))
        )


class TeamViewSet(ReadOnlyViewSet):
    """Every team the scraper has seen, with the crest the listings draw."""

    queryset = Team.objects.prefetch_related("favorite")
    serializer_class = TeamSerializer
    query_filters = (
        filtering.switch(
            "favorite",
            "Only teams on the owner's curated list.",
            lambda queryset: queryset.filter(favorite__isnull=False).distinct(),
        ),
        filtering.switch(
            "has_crest",
            "Only teams carrying a crest, which is the set the strips on the site show.",
            lambda queryset: queryset.filter(WITH_A_CREST),
        ),
        filtering.free_text("Case-insensitive match on the name.", "name"),
    )


class FlagViewSet(ReadOnlyViewSet):
    """The flags competitions are shown with."""

    queryset = Flag.objects.all()
    serializer_class = FlagSerializer
    query_filters = (filtering.free_text("Case-insensitive match on either name.", "name", "display_name"),)


class ChannelViewSet(ReadOnlyViewSet):
    """The channels events are broadcast on, each with the links it carries."""

    queryset = Channel.objects.prefetch_related("links__sources")
    serializer_class = ChannelSerializer
    query_filters = (
        filtering.switch(
            "has_enabled_links",
            "Only channels carrying at least one enabled link.",
            lambda queryset: queryset.filter(links__enabled=True).distinct(),
        ),
        filtering.free_text("Case-insensitive match on the name.", "name"),
    )


def only_playable(queryset: QuerySet[ChannelLink]) -> QuerySet[ChannelLink]:
    """The links the site would actually render as an `href`.

    `has_allowed_scheme` reads the scheme with `urlparse`, which no database can do, so the
    same question is asked here as a prefix match. `test_api_channels.py` compares the two
    over the rows a test writes past `save()` — the state production can hold and a local
    database cannot, since only a migration, a fixture or an `UPDATE` can store a link the
    model's own validation would refuse.
    """
    allowed = Q()
    for scheme in ALLOWED_LINK_SCHEMES:
        allowed |= Q(link__istartswith=f"{scheme}://")
    return queryset.filter(allowed)


class ChannelLinkViewSet(ReadOnlyViewSet):
    """Every link in the directory, in the order `/channels/` shows them."""

    queryset = ChannelLink.objects.prefetch_related("sources")
    serializer_class = ChannelLinkSerializer
    query_filters = (
        filtering.toggle("enabled", "Whether the link is enabled.", "enabled"),
        filtering.toggle("verified", "Whether the link has been checked.", "verified"),
        filtering.switch("playable", "Only links whose scheme the site will render.", only_playable),
        filtering.exact("quality", "Exact quality label.", "quality", choices=tuple(ChannelLink.Quality.values)),
        filtering.exact("category", "Exact category.", "category"),
        filtering.exact("subcategory", "Exact subcategory.", "subcategory"),
        filtering.identifier("source", "Only links carried by this source.", "sources__pk"),
        filtering.free_text("Case-insensitive match on the name.", "name"),
    )


class ChannelLinkSourceViewSet(ReadOnlyViewSet):
    """Where the links came from: one row per imported list."""

    queryset = ChannelLinkSource.objects.all()
    serializer_class = ChannelLinkSourceSerializer
    query_filters = (filtering.toggle("enabled", "Whether the source is enabled.", "enabled"),)


class FavoriteViewSet(ReadOnlyViewSet):
    """The owner's curated favourites, which is what the landing page shows a visitor who has chosen none.

    A visitor's own choices live in a signed cookie and never on the server, so they are not
    here and cannot be: there is nothing to read them from.
    """

    queryset = Favorite.objects.select_related("competition__sport", "competition__flag", "team").prefetch_related(
        "competition__favorite", "team__favorite"
    )
    serializer_class = FavoriteSerializer
    query_filters = (
        QueryFilter(
            name="kind",
            description="Only rows naming a team, or only those naming a competition.",
            narrow=lambda queryset, value: queryset.filter(**{f"{value}__isnull": False}),
            parse=filtering.one_of(("team", "competition")),
            choices=("team", "competition"),
        ),
    )


class EventViewSet(ReadOnlyViewSet):
    """Every event the site knows about, whatever kind, in one chronological listing.

    Nothing is filtered out by default — what has already happened is information the site
    holds — so a client wanting the agenda asks for `today_onwards`, and one wanting the
    landing page asks for `upcoming`.
    """

    queryset = Event.objects.all()
    serializer_class = EventSerializer
    query_filters = (
        filtering.exact(
            "event_type",
            "Only events of this kind.",
            "event_type",
            choices=tuple(Event.EventType.values),
        ),
        filtering.identifier("competition", "Only events of this competition.", "competition__pk"),
        filtering.identifier("sport", "Only events of this sport.", "competition__sport__pk"),
        QueryFilter(
            name="team",
            description="Only matches this team plays, at home or away.",
            narrow=lambda queryset, value: queryset.for_team(value),
            parse=filtering.as_integer,
            schema_type=OpenApiTypes.INT,
        ),
        filtering.identifier("channel", "Only events broadcast on this channel.", "channels__pk"),
        filtering.day("date", "Only events on this day, read in Europe/Madrid.", lambda qs, day: qs.for_date(day)),
        filtering.day("date_from", "Only events on or after this day.", lambda qs, day: qs.on_or_after(day)),
        filtering.day("date_to", "Only events on or before this day.", lambda qs, day: qs.on_or_before(day)),
        QueryFilter(
            name="search",
            description="Case-insensitive match on the teams, the race or event name, the competition or the sport.",
            narrow=lambda queryset, value: queryset.search(value),
        ),
        filtering.switch("watchable", "Only events with at least one enabled link.", lambda qs: qs.watchable()),
        filtering.switch(
            "favorites",
            "Only events on the owner's curated list: a match of a favourite team, or a race or "
            "simple event of a favourite competition.",
            lambda queryset: queryset.favorites(),
        ),
        filtering.switch(
            "upcoming",
            "Only events that have not finished: from three hours ago onwards, which is how long "
            "the site keeps one on screen.",
            lambda queryset: queryset.in_progress_or_upcoming(),
        ),
        filtering.switch(
            "today_onwards",
            "Only events from the start of today, read in Europe/Madrid.",
            lambda queryset: queryset.today_onwards(),
        ),
        filtering.ordering(
            "By start time, ascending by default.",
            {"date": CHRONOLOGICAL, "-date": REVERSE_CHRONOLOGICAL},
        ),
    )

    def get_queryset(self) -> QuerySet[Event]:
        """The relations every row walks, preloaded exactly once.

        `with_related()` is what the site's own listings use; the sources of each link are
        the one thing it does not reach, because no page prints them. Added as a deeper
        lookup on top of the prefetch it already declares rather than as a second `Prefetch`
        of `channels`, which Django refuses.
        """
        return Event.objects.with_related().prefetch_related("channels__links__sources").chronological()

    @extend_schema(
        description=(
            "The local days — read in Europe/Madrid, like every day here — holding at least "
            "one event, under the same filters the listing takes. What a calendar needs to "
            "light its days without downloading the events behind them."
        ),
        responses=inline_serializer(
            name="EventDays",
            fields={"days": serializers.ListField(child=serializers.DateField())},
        ),
    )
    @action(detail=False)
    def days(self, request: Request) -> Response:
        """One sorted list of dates, however many events each carries.

        The start times are read bare and grouped in Python rather than with a database
        `DISTINCT` over a date function: the dates are stored in UTC, "which day" is a
        question about Europe/Madrid, and SQLite's date arithmetic knows nothing about
        either. The whole table is a few tens of thousands of one-column rows at worst,
        and every filter the listing takes narrows it first.
        """
        starts = self.filter_queryset(Event.objects.all()).values_list("date", flat=True)
        days = sorted({localtime(start).date() for start in starts})
        return Response({"days": [day.isoformat() for day in days]})


class ApiRootView(routers.APIRootView):
    """Every collection, and where the description of them lives.

    A caller who found `/api/v1/` and nothing else must be able to reach the schema from
    here; otherwise the only way to learn the API is to read this file.
    """

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        response = super().get(request, *args, **kwargs)
        response.data["schema"] = reverse("api-schema", request=request)
        response.data["docs"] = reverse("api-docs", request=request)
        return response


class ApiDocsView(TemplateView):
    """Swagger UI, served from this origin.

    The stock page loads the library from a CDN and starts it from an inline script, and
    this site's Content-Security-Policy refuses both. So the assets come from the sidecar
    package through `collectstatic`, and the initialisation lives in a static file that
    reads the schema URL from a data attribute.
    """

    template_name = "soccertime/api_docs.html"
