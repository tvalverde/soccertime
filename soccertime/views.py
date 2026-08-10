from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.cache import cache_page

from soccertime.models import CHANNEL_LINK_ORDERING, Channel, ChannelLink, Competition, Event, Sport, Team

# --- Helper functions ---


def get_favorite_competitions():
    """Get competitions marked as favorites, ordered by preference."""
    return (
        Competition.objects.filter(
            favorite__isnull=False,
            events__date__date__gte=timezone.now().date(),
        )
        .select_related("flag")
        .distinct()
        .order_by("favorite__order")
    )


def get_favorite_teams():
    """Get teams marked as favorites, ordered by preference."""
    return (
        Team.objects.filter(favorite__isnull=False)
        .exclude(Q(crest__isnull=True) | Q(crest=""))
        .order_by("favorite__order")
    )


def get_base_context():
    """Get common context data used across multiple views."""
    return {
        "competitions": get_favorite_competitions(),
        "teams": get_favorite_teams(),
    }


def parse_requested_date(value):
    """Parse a user supplied date, returning None when it is missing or malformed."""
    if not value:
        return None
    try:
        return parse_date(value)
    except ValueError:
        return None


def paginate_queryset(queryset, request, per_page=25):
    """Paginate a queryset consistently across views."""
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def empty_state(message="No hay eventos a la vista :)", level="info"):
    """Notice the templates render when the listing turns out to be empty.

    It travels in the context instead of the messages framework: these views are
    cached as a whole, and a per-request message would be baked into the shared
    page cache and served to everybody else.
    """
    return {"empty_message": message, "empty_message_level": level}


# --- Views ---


def healthz(request):
    return JsonResponse({"status": "ok"})


@cache_page(settings.CACHE_PAGE_TIMEOUT)
def favorites(request):
    queryset = Event.objects.favorites().in_window(hours_before=3, days_ahead=3).with_related().chronological()

    context = get_base_context()
    context.pop("teams", None)
    context.update({"events": queryset})
    context.update(empty_state("No hay eventos a la vista :(", "warning"))
    return render(request, "soccertime/agenda.html", context)


@cache_page(settings.CACHE_PAGE_TIMEOUT)
def agenda(request):
    max_date_result = Event.objects.aggregate(Max("date"))["date__max"]
    max_date = max_date_result.strftime("%Y-%m-%d") if max_date_result else None

    requested_date = parse_requested_date(request.GET.get("events-date"))
    if requested_date:
        queryset = Event.objects.for_date(requested_date).with_related()
    else:
        queryset = Event.objects.today_onwards().with_related()

    queryset = queryset.search(request.GET.get("search")).chronological()

    context = get_base_context()
    context.update(
        {
            "events": paginate_queryset(queryset, request),
            "max_date": max_date,
        }
    )
    context.update(empty_state())
    return render(request, "soccertime/agenda.html", context)


@cache_page(settings.CACHE_PAGE_TIMEOUT)
def team_events(request, team):
    team_obj = get_object_or_404(Team, pk=team)
    queryset = Event.objects.for_team(team).in_progress_or_upcoming().with_related().chronological()

    # Obtener equipos rivales en partidos futuros, ordenados por fecha de enfrentamiento
    now = timezone.now()

    # Obtener IDs de partidos futuros del equipo
    from soccertime.models import Match

    future_matches = Match.objects.select_related("local", "visitor").filter(
        Q(local=team_obj) | Q(visitor=team_obj), date__gte=now
    )

    # Obtener equipos rivales con la fecha del próximo enfrentamiento
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

    # Ordenar equipos por fecha de enfrentamiento, excluyendo los que no tienen escudo
    competition_teams = sorted(
        Team.objects.filter(id__in=opponent_ids).exclude(Q(crest__isnull=True) | Q(crest="")),
        key=lambda t: opponent_dates.get(t.id),
    )

    return render(
        request,
        "soccertime/agenda.html",
        {
            "events": queryset,
            "events_title": team_obj.name,
            "competitions": get_favorite_competitions(),
            "competition_teams": competition_teams,
            **empty_state(),
        },
    )


@cache_page(settings.CACHE_PAGE_TIMEOUT)
def channel_events(request, channel):
    channel_obj = get_object_or_404(Channel, pk=channel)
    queryset = Event.objects.for_channel(channel).in_progress_or_upcoming().with_related().chronological()

    context = get_base_context()
    context.pop("teams", None)
    context.update(
        {
            "events": queryset,
            "events_title": channel_obj.name,
        }
    )
    context.update(empty_state())
    return render(request, "soccertime/agenda.html", context)


@cache_page(settings.CACHE_PAGE_TIMEOUT)
def sport_events(request, sport):
    sport_obj = get_object_or_404(Sport, pk=sport)
    queryset = Event.objects.for_sport(sport).in_progress_or_upcoming().with_related().chronological()

    context = get_base_context()
    context.pop("teams", None)
    context.update(
        {
            "events": paginate_queryset(queryset, request),
            "events_title": sport_obj.name,
        }
    )
    context.update(empty_state())
    return render(request, "soccertime/agenda.html", context)


@cache_page(settings.CACHE_PAGE_TIMEOUT)
def competition_events(request, competition):
    competition_obj = get_object_or_404(Competition, pk=competition)
    queryset = Event.objects.for_competition(competition).in_progress_or_upcoming().with_related().chronological()

    return render(
        request,
        "soccertime/agenda.html",
        {
            "events": queryset,
            "events_title": competition_obj.name,
            "competitions": get_favorite_competitions(),
            "competition_teams": Team.objects.filter(
                Q(home_matches__competition=competition_obj) | Q(away_matches__competition=competition_obj)
            )
            .exclude(Q(crest__isnull=True) | Q(crest=""))
            .order_by("name")
            .distinct(),
            **empty_state(),
        },
    )


@cache_page(settings.CACHE_PAGE_TIMEOUT)
def channels(request):
    # The template regroups by subcategory, category and name; those keys come first so
    # the grouping works, and the model's own ordering decides the order inside each card.
    # Without it the links of a card come back in whatever order the database chose.
    queryset = ChannelLink.objects.order_by("category", "subcategory", "name", *CHANNEL_LINK_ORDERING)
    return render(
        request,
        "soccertime/channels.html",
        {
            "channels_links": queryset,
            **empty_state("No hay canales disponibles :_(", "danger"),
        },
    )


@cache_page(settings.CACHE_PAGE_TIMEOUT)
def competitions(request):
    """
    Exhibe deportes y sus competiciones, optimizado para evitar N+1 queries.
    """
    from django.db.models import Exists, OuterRef, Q

    from soccertime.models import Favorite

    today = timezone.now().date()

    # 1. Obtener deportes activos (con eventos próximos)
    active_sports = (
        Sport.objects.with_events().annotate(num_comps=Count("competitions")).order_by("-num_comps", "name").distinct()
    )

    # 2. Obtener todas las competiciones de esos deportes con anotaciones
    competitions_qs = (
        Competition.objects.filter(sport__in=active_sports)
        .select_related("flag")
        .annotate(
            num_events=Count("events", filter=Q(events__date__date__gte=today)),
            is_fav=Exists(Favorite.objects.filter(competition=OuterRef("pk"))),
        )
    )

    # 3. Agrupar datos en Python
    sports_map = {sport.id: {"sport": sport, "with_events": [], "without_events": []} for sport in active_sports}

    for comp in competitions_qs:
        sport_id = comp.sport_id
        if sport_id in sports_map:
            if comp.num_events > 0:
                sports_map[sport_id]["with_events"].append(comp)
            else:
                sports_map[sport_id]["without_events"].append(comp)

    # Ordenar las listas de competiciones con eventos por número de eventos (desc) y nombre
    for data in sports_map.values():
        data["with_events"].sort(key=lambda x: (-x.num_events, x.name))
        data["without_events"].sort(key=lambda x: x.name)

    # Preparar el contexto final manteniendo el orden de los deportes
    sports_data = [sports_map[sport.id] for sport in active_sports]

    return render(
        request,
        "soccertime/competitions.html",
        {
            "sports_data": sports_data,
            "competitions": get_favorite_competitions(),
        },
    )
