from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Max, Min, Q
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from soccertime.models import Event, ChannelLink, Team, Channel, Sport, Competition


# --- Helper functions ---

def get_favorite_competitions():
    """Get competitions marked as favorites, ordered by preference."""
    return Competition.objects.filter(favorite__isnull=False).order_by('favorite__order')


def get_favorite_teams():
    """Get teams marked as favorites, ordered by preference."""
    return Team.objects.filter(favorite__isnull=False).order_by('favorite__order')


def get_base_context():
    """Get common context data used across multiple views."""
    return {
        "competitions": get_favorite_competitions(),
        "teams": get_favorite_teams(),
    }


def paginate_queryset(queryset, request, per_page=25):
    """Paginate a queryset consistently across views."""
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def add_empty_message(request, queryset, message="No hay eventos a la vista :)", level=messages.INFO):
    """Add a message if queryset is empty."""
    if not queryset.exists():
        messages.add_message(request, level, message)


# --- Views ---

def favorites(request):
    queryset = Event.objects.favorites().in_window(hours_before=3, days_ahead=3)
    add_empty_message(request, queryset, "No hay eventos a la vista :(", messages.WARNING)
    return render(
        request,
        "soccertime/agenda.html",
        {
            "events": queryset,
            "competitions": get_favorite_competitions(),
        },
    )


def agenda(request):
    max_date_result = Event.objects.aggregate(Max('date'))['date__max']
    max_date = max_date_result.strftime('%Y-%m-%d') if max_date_result else None

    if request.GET.get('events-date'):
        queryset = Event.objects.for_date(request.GET.get('events-date'))
    else:
        queryset = Event.objects.today_onwards()

    queryset = queryset.search(request.GET.get('search')).order_by('date')
    add_empty_message(request, queryset)

    context = get_base_context()
    context.update({
        "events": paginate_queryset(queryset, request),
        "max_date": max_date,
    })
    return render(request, "soccertime/agenda.html", context)


def team_events(request, team):
    team_obj = get_object_or_404(Team, pk=team)
    queryset = Event.objects.for_team(team).in_progress_or_upcoming()
    add_empty_message(request, queryset)

    # Obtener equipos rivales en partidos futuros, ordenados por fecha de enfrentamiento
    now = timezone.now()

    # Obtener IDs de partidos futuros del equipo
    from soccertime.models import Match
    future_matches = Match.objects.filter(
        Q(local=team_obj) | Q(visitor=team_obj),
        date__gte=now
    )

    # Obtener equipos rivales con la fecha del próximo enfrentamiento
    opponent_ids = set()
    opponent_dates = {}

    for match in future_matches.order_by('date'):
        if match.local == team_obj:
            opponent = match.visitor
        else:
            opponent = match.local

        if opponent.id not in opponent_ids:
            opponent_ids.add(opponent.id)
            opponent_dates[opponent.id] = match.date

    # Ordenar equipos por fecha de enfrentamiento
    competition_teams = sorted(
        Team.objects.filter(id__in=opponent_ids),
        key=lambda t: opponent_dates.get(t.id)
    )

    return render(
        request,
        "soccertime/agenda.html",
        {
            "events": queryset,
            "events_title": team_obj.name,
            "competitions": get_favorite_competitions(),
            "competition_teams": competition_teams,
        },
    )


def channel_events(request, channel):
    channel_obj = get_object_or_404(Channel, pk=channel)
    queryset = Event.objects.for_channel(channel).in_progress_or_upcoming()
    add_empty_message(request, queryset)
    return render(
        request,
        "soccertime/events.html",
        {
            "events": queryset,
            "events_title": channel_obj.name,
        },
    )


def sport_events(request, sport):
    sport_obj = get_object_or_404(Sport, pk=sport)
    queryset = Event.objects.for_sport(sport).in_progress_or_upcoming()
    add_empty_message(request, queryset)
    return render(
        request,
        "soccertime/events.html",
        {
            "events": paginate_queryset(queryset, request),
            "events_title": sport_obj.name,
        },
    )


def competition_events(request, competition):
    competition_obj = get_object_or_404(Competition, pk=competition)
    queryset = Event.objects.for_competition(competition).in_progress_or_upcoming()
    add_empty_message(request, queryset)

    return render(
        request,
        "soccertime/agenda.html",
        {
            "events": queryset,
            "events_title": competition_obj.name,
            "competitions": get_favorite_competitions(),
            "competition_teams": Team.objects.filter(
                Q(home_matches__competition=competition_obj) |
                Q(away_matches__competition=competition_obj)
            ).order_by('name').distinct(),
        },
    )


def channels(request):
    queryset = ChannelLink.objects.order_by("category", "subcategory", "name")
    add_empty_message(request, queryset, "No hay canales disponibles :_(", messages.ERROR)
    return render(
        request,
        "soccertime/channels.html",
        {"channels_links": queryset},
    )


def competitions(request):
    queryset = Sport.objects.with_events().annotate(
        count=Count('competitions')
    ).order_by('-count', 'name').distinct()

    return render(
        request,
        "soccertime/competitions.html",
        {
            "sports": queryset,
            "competitions": get_favorite_competitions(),
        },
    )
