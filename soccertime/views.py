import datetime
from functools import wraps
from typing import Any

from django.conf import settings
from django.core.paginator import Page, Paginator
from django.db.models import Count, Exists, Max, OuterRef, Q, QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.dateparse import parse_date
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_control, cache_page
from django.views.decorators.http import require_POST

from soccertime.models import (
    CHANNEL_LINK_ORDERING,
    Channel,
    ChannelLink,
    Competition,
    Event,
    Favorite,
    Match,
    Sport,
    Team,
    start_of_today,
)
from soccertime.visitor_favorites import EntityKind, Selection, read_selection, write_selection


def cached_page(view: Any) -> Any:
    """Cache the rendered page on the server, and make the browser ask before reusing it.

    `cache_page` announces its own timeout to the client as `Cache-Control: max-age`, so a
    visitor who had loaded a page went on serving it from their own cache for the next hour
    without contacting the server at all. That is wrong for a listing of live events: the
    scraper runs and `make remote-scrape` clears the server cache, and none of it reached
    anybody who had just been on the site. It also meant a deploy took up to an hour to
    become visible to a returning visitor.

    The server cache is untouched — the expensive part is still computed once an hour. What
    goes is the browser's licence to skip the request. `ConditionalGetMiddleware` answers
    the resulting revalidation with a 304 and no body whenever the page has not changed, so
    the cost is a round trip rather than a re-render or a re-download.

    Applied outside `cache_page` so it also patches responses that come back from the
    cache, including ones stored before this existed.

    The timeout is read per request rather than when this module is imported. Reading it at
    import time is the usual Django footgun — it binds whatever the setting happened to be
    while the module loaded, so nothing can change it afterwards and no test can turn the
    server cache on to check it is still there.
    """

    @wraps(view)
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        decorated = cache_control(max_age=0, must_revalidate=True)(cache_page(settings.CACHE_PAGE_TIMEOUT)(view))
        return decorated(request, *args, **kwargs)

    return wrapped


def cached_unless_personalised(view: Any) -> Any:
    """Cache the page for everybody who has chosen nothing, and nobody else.

    The shared cache is keyed by URL, so a page that differs per visitor cannot go in it.
    Rather than key it by cookie — which would let anyone mint entries by sending cookies
    and push the real pages out of a store that holds three hundred — the visitors who carry
    a selection are simply served fresh. They are the few; everybody arriving without one,
    which includes every crawler, shares the single cached copy exactly as before.

    What counts as carrying one is a **valid signature**, not a cookie of that name. Testing
    the name alone made the cache switchable off from outside: `Cookie: soccertime_favorites=x`
    is unsigned, so the view rendered the ordinary curated page — freshly, every time, with no
    rate limit in front of it. Measured at 1.9-2.3s per request on `/competitions/` against
    production data, which is half a request per second to saturate the container that also
    serves the database. Verifying the signature costs one HMAC over a hundred bytes.

    `Vary: Cookie` is sent either way, so no proxy in between reuses one visitor's page for
    another, and the fresh branch is marked `private` so nothing between here and them may
    store it at all. The stored copy is learnt from a request that carried no selection, so
    the key stays the plain URL and the entry cannot fragment.
    """

    @wraps(view)
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if read_selection(request) is None:
            response = cached_page(view)(request, *args, **kwargs)
        else:
            response = cache_control(private=True, max_age=0, must_revalidate=True)(view)(request, *args, **kwargs)
        patch_vary_headers(response, ("Cookie",))
        return response

    return wrapped


# The site is served in Spanish; these are wrapped so a future locale can translate them.
NO_EVENTS_MESSAGE = _("No hay eventos a la vista :)")
NO_FAVOURITE_EVENTS_MESSAGE = _("No hay eventos a la vista :(")
NO_WATCHABLE_EVENTS_MESSAGE = _("Ninguno de estos eventos tiene enlace para verlo")
NO_CHANNELS_MESSAGE = _("No hay canales disponibles :_(")

# --- Helper functions ---


def get_favorite_competitions(selection: Selection | None = None) -> list[Competition]:
    """The flag strip above every listing: the visitor's competitions, or the owner's.

    Kept to competitions with something still to come either way, which is what makes it a
    shortcut rather than an archive. A visitor's own are ordered by when they starred them,
    which the cookie preserves; the owner's keep the order they were dragged into.
    """
    upcoming = Competition.objects.filter(events__date__gte=start_of_today()).select_related("flag").distinct()
    if selection is None:
        return list(upcoming.filter(favorite__isnull=False).order_by("favorite__order"))
    chosen = upcoming.filter(pk__in=selection.competitions)
    return sorted(chosen, key=lambda competition: selection.competitions.index(competition.pk))


def get_favorite_teams(selection: Selection | None = None) -> list[Team]:
    """The crest strip, which only the agenda carries. A team with no crest has nothing to show."""
    with_crest = Team.objects.exclude(Q(crest__isnull=True) | Q(crest=""))
    if selection is None:
        return list(with_crest.filter(favorite__isnull=False).order_by("favorite__order"))
    chosen = with_crest.filter(pk__in=selection.teams)
    return sorted(chosen, key=lambda team: selection.teams.index(team.pk))


def personalised(view: Any) -> Any:
    """A page that shows the visitor their own state, and therefore never enters the cache.

    These carry the star, and a star is a form, and a form carries a CSRF token. Django sets
    `Set-Cookie: csrftoken` on the response that renders one — stored in a cache shared by
    everybody, that token and that cookie would be handed to every other visitor, which is
    precisely what the protection exists to prevent. It is the same shape as the per-request
    message that leaked into the shared cache once before, with a security token in the
    place of a notice. A test asserts that no cached page renders one.

    `private` is the half that matters to everything between here and the visitor: without a
    Cache-Control header at all, a proxy is free to store what it likes and hand it on. The
    rest matches the shared pages, so the browser still revalidates and still gets a 304.
    """

    @wraps(view)
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        decorated = cache_control(private=True, max_age=0, must_revalidate=True)(view)
        response = decorated(request, *args, **kwargs)
        patch_vary_headers(response, ("Cookie",))
        return response

    return wrapped


def get_star_context(kind: EntityKind, entity_id: int, selection: Selection | None) -> dict[str, Any]:
    """What a page needs to offer its own team or competition as a favourite.

    The destination is built from the entity rather than taken from the request, so there is
    no parameter naming where to go afterwards and no open redirect to get wrong.
    """
    return {
        "star_action": reverse(f"toggle-favorite-{kind}", args=[entity_id]),
        "star_is_favorite": selection is not None and selection.holds(kind, entity_id),
    }


def get_base_context(with_teams: bool = False, selection: Selection | None = None) -> dict[str, Any]:
    """Context every listing shares.

    Only the agenda shows the favourite teams strip, so the rest do not pay for the
    query; the views used to ask for it and pop it back out.

    `selection` travels into the context as well, because the gold border marking a
    favourite row is decided per visitor for the same reason the strips are: a page filtered
    to one person's teams, under a strip of somebody else's, beside rows bordered as a
    third's, would contradict itself three ways.
    """
    context: dict[str, Any] = {
        "competitions": get_favorite_competitions(selection),
        "selection": selection,
    }
    if with_teams:
        context["teams"] = get_favorite_teams(selection)
    return context


def parse_requested_date(value: str | None) -> datetime.date | None:
    """Parse a user supplied date, returning None when it is missing or malformed."""
    if not value:
        return None
    try:
        return parse_date(value)
    except ValueError:
        return None


def paginate_queryset(
    queryset: QuerySet[Any], request: HttpRequest, per_page: int = 25, default_page: int = 1
) -> Page[Any]:
    """Paginate a queryset consistently across views.

    `default_page` is what the listing opens on when the request names none. An explicit
    `?page=` always wins, so every link the pagination widget builds keeps working.
    """
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page") or default_page)


# How far back the agenda still counts as "the present" when deciding which page to open on.
# An anchor, not a filter: nothing is hidden, so being wrong costs a click rather than an
# event. Two hours because something that started within them is very likely still on, and
# opening past a match in progress is the one outcome worth avoiding.
#
# Filtering the past away instead was measured and rejected. Every event has `duration = NULL`,
# so "finished" is always the flat two-hour default, and 30% of future events are in sports
# where that is wrong — a cycling stage runs five hours, golf all day. No cutoff both hid
# enough and never hid something live: six hours still buried two live events at 21:00.
AGENDA_LOOKBACK = datetime.timedelta(hours=2)


def page_holding_the_present(queryset: QuerySet[Any], per_page: int = 25) -> int:
    """The page where a chronological listing reaches the present.

    The agenda begins at local midnight, so a visitor arriving in the evening used to read
    what had already happened: measured on a busy Saturday, roughly 71 of 127 rows were over
    by 18:00 and 115 by 22:00. This moves where the listing opens, and nothing else.
    """
    already_over = queryset.filter(date__lt=timezone.now() - AGENDA_LOOKBACK).count()
    return already_over // per_page + 1


def empty_state(message: "str | Promise" = NO_EVENTS_MESSAGE, level: str = "info") -> dict[str, Any]:
    """Notice the templates render when the listing turns out to be empty.

    It travels in the context instead of the messages framework: these views are
    cached as a whole, and a per-request message would be baked into the shared
    page cache and served to everybody else.
    """
    return {"empty_message": message, "empty_message_level": level}


# --- Views ---


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@cached_unless_personalised
def favorites(request: HttpRequest) -> HttpResponse:
    """The landing page: the visitor's own favourites, or the owner's when they have none.

    Filtered here rather than in the browser, which is what lets it paginate. A page that
    shipped the whole window for a script to sift could not: the server would be paginating
    events the visitor never wanted, so their own could land on page three and the first
    would look empty.
    """
    selection = read_selection(request)
    window = Event.objects.in_window(hours_before=3, days_ahead=3)
    if selection is None:
        window = window.favorites()
    else:
        window = window.for_selection(selection.teams, selection.competitions)

    context = get_base_context(selection=selection)
    context.update({"events": paginate_queryset(window.with_related().chronological(), request)})
    context.update(empty_state(NO_FAVOURITE_EVENTS_MESSAGE, "warning"))
    return render(request, "soccertime/agenda.html", context)


@cached_unless_personalised
def agenda(request: HttpRequest) -> HttpResponse:
    max_date_result = Event.objects.aggregate(Max("date"))["date__max"]
    max_date = timezone.localtime(max_date_result).strftime("%Y-%m-%d") if max_date_result else None

    requested_date = parse_requested_date(request.GET.get("events-date"))
    if requested_date:
        queryset = Event.objects.for_date(requested_date).with_related()
    else:
        queryset = Event.objects.today_onwards().with_related()

    queryset = queryset.search(request.GET.get("search"))
    # Counted before the filter narrows it, so the control can say what it would show. Both
    # numbers are scoped to the date and the search already applied: a count that ignored them
    # would be worse than none, since it would not match the list underneath it.
    total_events = queryset.count()
    watchable_events = queryset.watchable().count()
    only_watchable = request.GET.get("watchable") == "1"
    if only_watchable:
        queryset = queryset.watchable()
    queryset = queryset.chronological()

    context = get_base_context(with_teams=True, selection=read_selection(request))
    # Asking for a specific day is asking for the whole of it, from its beginning; only the
    # rolling "today onwards" listing needs to be told where the present is.
    default_page = 1 if requested_date else page_holding_the_present(queryset)

    context.update(
        {
            "events": paginate_queryset(queryset, request, default_page=default_page),
            "max_date": max_date,
            "only_watchable": only_watchable,
            "total_events": total_events,
            "watchable_events": watchable_events,
        }
    )
    context.update(empty_state(NO_WATCHABLE_EVENTS_MESSAGE if only_watchable else NO_EVENTS_MESSAGE))
    return render(request, "soccertime/agenda.html", context)


@personalised
def team_events(request: HttpRequest, team: int) -> HttpResponse:
    team_obj = get_object_or_404(Team, pk=team)
    selection = read_selection(request)
    queryset = Event.objects.for_team(team).in_progress_or_upcoming().with_related().chronological()

    # Opponents in upcoming matches, ordered by when they are played
    now = timezone.now()

    # Upcoming matches for this team
    future_matches = Match.objects.select_related("local", "visitor").filter(
        Q(local=team_obj) | Q(visitor=team_obj), date__gte=now
    )

    # Keep each opponent once, at the date of the next meeting
    opponent_ids = set()
    opponent_dates = {}

    for match in future_matches.order_by("date"):
        if match.local == team_obj:
            opponent = match.visitor
        else:
            opponent = match.local

        if opponent.id not in opponent_ids:
            opponent_ids.add(opponent.id)
            opponent_dates[opponent.id] = match.date

    # Ordered by that date, skipping the ones with no crest to show
    competition_teams = sorted(
        Team.objects.filter(id__in=opponent_ids).exclude(Q(crest__isnull=True) | Q(crest="")),
        key=lambda team: opponent_dates[team.id],
    )

    context = get_base_context(selection=selection)
    context.update(
        {
            # Paginated because this page carries a form and so cannot be shared-cached: what
            # used to be rendered once an hour is now rendered on every visit, and an
            # unbounded listing turns that into the site's slowest page. Measured against
            # production data, a busy competition took 1.6s to render whole.
            "events": paginate_queryset(queryset, request),
            "events_title": team_obj.name,
            "competition_teams": competition_teams,
            **get_star_context("team", team_obj.pk, selection),
            **empty_state(),
        }
    )
    return render(request, "soccertime/agenda.html", context)


@cached_unless_personalised
def channel_events(request: HttpRequest, channel: int) -> HttpResponse:
    channel_obj = get_object_or_404(Channel, pk=channel)
    queryset = Event.objects.for_channel(channel).in_progress_or_upcoming().with_related().chronological()

    context = get_base_context(selection=read_selection(request))
    context.update(
        {
            "events": queryset,
            "events_title": channel_obj.name,
        }
    )
    context.update(empty_state())
    return render(request, "soccertime/agenda.html", context)


@cached_unless_personalised
def sport_events(request: HttpRequest, sport: int) -> HttpResponse:
    sport_obj = get_object_or_404(Sport, pk=sport)
    queryset = Event.objects.for_sport(sport).in_progress_or_upcoming().with_related().chronological()

    context = get_base_context(selection=read_selection(request))
    context.update(
        {
            "events": paginate_queryset(queryset, request),
            "events_title": sport_obj.name,
        }
    )
    context.update(empty_state())
    return render(request, "soccertime/agenda.html", context)


def teams_playing_in(competition: Competition) -> QuerySet[Team]:
    """The crest strip on a competition's page: everyone who plays or has played in it.

    Read as two plain lookups rather than one `Q(home_matches=…) | Q(away_matches=…)`, which
    is the same question asked in the shape SQLite is worst at: that `OR` makes it join the
    52,000-row event table twice and then sort the result distinct. **Measured on production
    data for the NBA: 1,608 ms against 19 ms, for the same thirty teams in the same order.**

    It was affordable while the page was rendered once an hour. It is not now that the page
    carries a form and so cannot be shared-cached — which is how a query nobody had ever
    timed became the slowest thing on the site.
    """
    playing = Match.objects.filter(competition=competition).values_list("local_id", "visitor_id")
    team_ids = {team_id for pair in playing for team_id in pair}
    return Team.objects.filter(pk__in=team_ids).exclude(Q(crest__isnull=True) | Q(crest="")).order_by("name")


@personalised
def competition_events(request: HttpRequest, competition: int) -> HttpResponse:
    competition_obj = get_object_or_404(Competition, pk=competition)
    selection = read_selection(request)
    queryset = Event.objects.for_competition(competition).in_progress_or_upcoming().with_related().chronological()

    context = get_base_context(selection=selection)
    context.update(
        {
            "events": paginate_queryset(queryset, request),
            "events_title": competition_obj.name,
            **get_star_context("competition", competition_obj.pk, selection),
            "competition_teams": teams_playing_in(competition_obj),
            **empty_state(),
        }
    )
    return render(request, "soccertime/agenda.html", context)


def _toggle_favorite(request: HttpRequest, kind: EntityKind, entity_id: int, destination: str) -> HttpResponse:
    """Add or remove one entity from this visitor's own favourites.

    POST only, and answered with a redirect. A star that worked over GET would be pressed by
    every crawler that walked the site, and the redirect is what stops a reload from undoing
    what the visitor just did.

    The entity is looked up before anything is written, so an id that names nothing is a 404
    rather than a number stored in a cookie forever.
    """
    selection = read_selection(request) or Selection()
    response = redirect(destination, entity_id)
    return write_selection(response, selection.toggled(kind, entity_id))


@require_POST
def toggle_favorite_team(request: HttpRequest, team: int) -> HttpResponse:
    get_object_or_404(Team, pk=team)
    return _toggle_favorite(request, "team", team, "team-events")


@require_POST
def toggle_favorite_competition(request: HttpRequest, competition: int) -> HttpResponse:
    get_object_or_404(Competition, pk=competition)
    return _toggle_favorite(request, "competition", competition, "competition-events")


@cached_page
def channels(request: HttpRequest) -> HttpResponse:
    # The template regroups by subcategory, category and name; those keys come first so
    # the grouping works, and the model's own ordering decides the order inside each card.
    # Without it the links of a card come back in whatever order the database chose.
    queryset = ChannelLink.objects.order_by("category", "subcategory", "name", *CHANNEL_LINK_ORDERING)
    return render(
        request,
        "soccertime/channels.html",
        {
            "channels_links": queryset,
            **empty_state(NO_CHANNELS_MESSAGE, "danger"),
        },
    )


@cached_unless_personalised
def competitions(request: HttpRequest) -> HttpResponse:
    """List sports and their competitions, grouping in Python to avoid N+1 queries."""
    today = start_of_today()

    # Sports that still have upcoming events
    active_sports = (
        Sport.objects.with_events().annotate(num_comps=Count("competitions")).order_by("-num_comps", "name").distinct()
    )

    # Their competitions, annotated so the grouping needs no further queries
    competitions_qs = (
        Competition.objects.filter(sport__in=active_sports)
        .select_related("flag")
        .annotate(
            num_events=Count("events", filter=Q(events__date__gte=today)),
            is_fav=Exists(Favorite.objects.filter(competition=OuterRef("pk"))),
        )
    )

    # Group in Python rather than querying per sport
    sports_map: dict[int, dict[str, Any]] = {
        sport.id: {"sport": sport, "with_events": [], "without_events": []} for sport in active_sports
    }

    selection = read_selection(request)
    for comp in competitions_qs:
        # The annotation answers for the owner's list, which is the right answer for anybody
        # who has chosen nothing and the wrong one for everybody else. Overwritten in place
        # rather than queried differently, so the grouping below stays one query.
        if selection is not None:
            comp.is_fav = comp.pk in selection.competitions
        sport_id = comp.sport_id
        if sport_id in sports_map:
            if comp.num_events > 0:
                sports_map[sport_id]["with_events"].append(comp)
            else:
                sports_map[sport_id]["without_events"].append(comp)

    # Busiest competitions first, then alphabetically
    for data in sports_map.values():
        data["with_events"].sort(key=lambda x: (-x.num_events, x.name))
        data["without_events"].sort(key=lambda x: x.name)

    # Preserve the sport ordering established above
    sports_data = [sports_map[sport.id] for sport in active_sports]

    context = get_base_context(selection=selection)
    context.update({"sports_data": sports_data})
    return render(request, "soccertime/competitions.html", context)
