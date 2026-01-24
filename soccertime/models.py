import datetime
import hashlib
import os
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _


class SportManager(models.Manager):
    def with_events(self):
        return self.filter(competitions__events__date__date__gte=timezone.now().date()).distinct()


class Sport(models.Model):
    name = models.CharField(max_length=255, unique=True)
    order = models.PositiveIntegerField(default=0, blank=False, null=False, db_index=True)

    objects = SportManager()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name

    @property
    def competitions_with_events(self):
        """Retorna competiciones con eventos próximos, ordenadas por cantidad de eventos."""
        today = timezone.now().date()
        return (
            self.competitions.filter(events__date__date__gte=today)
            .distinct()
            .annotate(num_events=models.Count("events", filter=models.Q(events__date__date__gte=today)))
            .order_by("-num_events", "name")
        )

    @property
    def competitions_without_events(self):
        """Retorna competiciones sin eventos próximos."""
        today = timezone.now().date()
        return self.competitions.exclude(events__date__date__gte=today).order_by("name")


def gen_upload_to(instance, filename):
    return f"{instance.IMG_PARENT_DIR}/{filename[:2]}/{filename[2:4]}/{filename}"


class ImageMixin(models.Model):
    """
    Mixin for models that have an image field with:
    - Upload path based on content hash
    - Fallback SVG when image is missing
    - HTML rendering method
    """

    IMG_PARENT_DIR = ""  # Override in subclass
    IMG_FIELD_NAME = "image"  # Override if field has different name
    IMG_WIDTH_DIVISOR = 1  # For scaling in HTML output

    FALLBACK_SVG = """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-emoji-dizzy" viewBox="0 0 16 16">
          <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16"/>
          <path d="M9.146 5.146a.5.5 0 0 1 .708 0l.646.647.646-.647a.5.5 0 0 1 .708.708l-.647.646.647.646a.5.5 0 0 1-.708.708l-.646-.647-.646.647a.5.5 0 1 1-.708-.708l.647-.646-.647-.646a.5.5 0 0 1 0-.708m-5 0a.5.5 0 0 1 .708 0l.646.647.646-.647a.5.5 0 1 1 .708.708l-.647.646.647.646a.5.5 0 1 1-.708.708L5.5 7.207l-.646.647a.5.5 0 1 1-.708-.708l.647-.646-.647-.646a.5.5 0 0 1 0-.708M10 11a2 2 0 1 1-4 0 2 2 0 0 1 4 0"/>
        </svg>
    """

    class Meta:
        abstract = True

    def _get_image_field(self):
        """Get the image field instance."""
        return getattr(self, self.IMG_FIELD_NAME)

    def render_image(self):
        """Render HTML for the image with fallback SVG."""
        image = self._get_image_field()
        if not image or not image.storage.exists(image.name):
            return self.FALLBACK_SVG
        width = image.width / self.IMG_WIDTH_DIVISOR
        height = image.height / self.IMG_WIDTH_DIVISOR
        return f'<img src="{image.url}" width="{width}" height="{height}" />'

    def save_image(self, image_bytes, original_filename):
        """Save image from bytes, using content hash as filename."""
        filename = hashlib.sha1(image_bytes.getvalue()).hexdigest()
        ext = os.path.splitext(original_filename)[1]
        self._get_image_field().save(f"{filename}{ext}", image_bytes)
        self.save()


class Flag(ImageMixin, models.Model):
    IMG_PARENT_DIR = "flags"
    IMG_FIELD_NAME = "image"
    IMG_WIDTH_DIVISOR = 1.5

    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    image = models.ImageField(upload_to=gen_upload_to, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def flag_image(self):
        """Alias for backward compatibility."""
        return self.render_image()

    def save_flag(self, image, flag_filename):
        """Alias for backward compatibility."""
        self.save_image(image, flag_filename)


class Competition(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    sport = models.ForeignKey(Sport, related_name="competitions", on_delete=models.CASCADE)
    flag = models.ForeignKey(Flag, related_name="competitions", on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = (
            (
                "name",
                "sport",
            ),
        )
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"

    @property
    def is_favorite(self):
        return self.favorite.exists()

    @property
    def has_events(self):
        return self.events.filter(date__date__gte=timezone.now().date()).exists()

    @property
    def events_count(self):
        return self.events.filter(date__date__gte=timezone.now().date()).distinct().count()


class Team(ImageMixin, models.Model):
    IMG_PARENT_DIR = "crests"
    IMG_FIELD_NAME = "crest"
    IMG_WIDTH_DIVISOR = 1

    name = models.CharField(max_length=255, unique=True)
    crest = models.ImageField(upload_to=gen_upload_to, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def crest_image(self):
        """Alias for backward compatibility."""
        return self.render_image()

    def save_crest(self, crest, crest_filename):
        """Alias for backward compatibility."""
        self.save_image(crest, crest_filename)


class Favorite(models.Model):
    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, null=True, blank=True, related_name="favorite"
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name="favorite")
    order = models.PositiveIntegerField(default=0, blank=False, null=False, db_index=True)

    class Meta:
        unique_together = (
            (
                "competition",
                "team",
            ),
        )
        ordering = ["order"]
        constraints = [
            models.CheckConstraint(
                condition=Q(competition__isnull=False) | Q(team__isnull=False),
                name="favorite_requires_competition_or_team",
            ),
        ]

    def __str__(self):
        if self.team:
            return f"{self.team} @ {self.competition}"
        return self.competition.name

    def clean(self):
        super().clean()
        if not self.competition and not self.team:
            raise ValidationError(_("At least one of competition or team must be set."))


class Channel(models.Model):
    name = models.CharField(max_length=255, unique=True)
    links = models.ManyToManyField("ChannelLink", related_name="channels", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def enabled_links(self):
        return self.links.filter(enabled=True)


class ChannelLink(models.Model):
    class Quality(models.TextChoices):
        ANY = "ANY", "ANY"
        UHD = "UHD", "UHD"
        FHD = "FHD", "FHD"
        HD = "HD", "HD"
        SD = "SD", "SD"

    category = models.CharField(max_length=255, null=True, blank=True)
    subcategory = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255)
    quality = models.CharField(max_length=255, choices=Quality, default=Quality.ANY)
    link = models.CharField(max_length=1000, null=True)
    source = models.CharField(max_length=255, null=True)
    date_added = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    enabled = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "channels links"
        unique_together = (
            (
                "link",
                "source",
            ),
        )
        ordering = ["-date_updated__date", "date_updated__time", "-verified", "-id"]

    def __str__(self):
        return f"{self.name} [{self.quality}]"

    @property
    def scheme(self):
        parsed_url = urlparse(self.link)
        return parsed_url.scheme


class EventQuerySet(models.QuerySet):
    """Custom QuerySet for Event model with chainable methods."""

    def in_progress_or_upcoming(self, hours_before=3):
        """Events that are in progress (started within hours_before) or upcoming."""
        return self.filter(date__gte=timezone.now() - datetime.timedelta(hours=hours_before))

    def in_window(self, hours_before=3, days_ahead=3):
        """Events within a time window: from hours_before ago to days_ahead in future."""
        now = timezone.now()
        return self.filter(
            date__gte=now - datetime.timedelta(hours=hours_before),
            date__lte=now + datetime.timedelta(days=days_ahead),
        )

    def today_onwards(self):
        """Events from the start of today onwards."""
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.filter(date__gte=today_start)

    def for_date(self, date):
        """Events on a specific date."""
        return self.filter(date__date=date)

    def for_date_range(self, start_date, end_date):
        """Events within a date range."""
        return self.filter(date__date__gte=start_date, date__date__lte=end_date)

    def upcoming_days(self, days=7):
        """Events in the next N days."""
        now = timezone.now()
        end_date = now + datetime.timedelta(days=days)
        return self.filter(date__gte=now, date__lte=end_date)

    def search(self, query):
        """Search events by team names, race name, or event name."""
        if not query:
            return self
        return self.filter(
            Q(match__local__name__icontains=query)
            | Q(match__visitor__name__icontains=query)
            | Q(race__name__icontains=query)
            | Q(simpleevent__name__icontains=query)
        )

    def favorites(self):
        """Events involving favorite teams or favorite competitions (for non-match events)."""
        return self.filter(
            Q(match__local__favorite__isnull=False)
            | Q(match__visitor__favorite__isnull=False)
            | Q(race__competition__favorite__isnull=False)
            | Q(simpleevent__competition__favorite__isnull=False)
        )

    def for_team(self, team_id):
        """Events where team plays (home or away)."""
        return self.filter(Q(match__local__pk=team_id) | Q(match__visitor__pk=team_id))

    def for_competition(self, competition_id):
        """Events for a specific competition."""
        return self.filter(competition__pk=competition_id)

    def for_sport(self, sport_id):
        """Events for a specific sport."""
        return self.filter(competition__sport__pk=sport_id)

    def for_channel(self, channel_id):
        """Events broadcast on a specific channel."""
        return self.filter(channels__pk=channel_id)

    def by_type(self, event_type):
        """Filter by event type (match, race, simple)."""
        return self.filter(event_type=event_type)

    def matches(self):
        """Only match events."""
        return self.by_type("match")

    def races(self):
        """Only race events."""
        return self.by_type("race")

    def simple_events(self):
        """Only simple events."""
        return self.by_type("simple")

    def with_related(self):
        """Optimiza queries precargando relaciones comunes.

        Solo aplica select_related para relaciones que existen en el modelo actual.
        """
        qs = self

        # Relaciones comunes a todos los eventos
        qs = qs.select_related(
            "competition__sport",
            "competition__flag",
        ).prefetch_related(
            "channels",
        )

        # Solo añadir relaciones de subtipos si estamos en Event (no en Match/Race/SimpleEvent)
        if self.model._meta.model_name == "event":
            qs = qs.select_related(
                "match__local",
                "match__visitor",
                "race",
                "simpleevent",
            )

        return qs


class EventManager(models.Manager):
    """Custom manager for Event model."""

    def get_queryset(self):
        return EventQuerySet(self.model, using=self._db).with_related()

    def in_progress_or_upcoming(self, hours_before=3):
        return self.get_queryset().in_progress_or_upcoming(hours_before)

    def in_window(self, hours_before=3, days_ahead=3):
        return self.get_queryset().in_window(hours_before, days_ahead)

    def today_onwards(self):
        return self.get_queryset().today_onwards()

    def for_date(self, date):
        return self.get_queryset().for_date(date)

    def for_date_range(self, start_date, end_date):
        return self.get_queryset().for_date_range(start_date, end_date)

    def upcoming_days(self, days=7):
        return self.get_queryset().upcoming_days(days)

    def favorites(self):
        return self.get_queryset().favorites()

    def search(self, query):
        return self.get_queryset().search(query)

    def for_team(self, team_id):
        return self.get_queryset().for_team(team_id)

    def for_competition(self, competition_id):
        return self.get_queryset().for_competition(competition_id)

    def for_sport(self, sport_id):
        return self.get_queryset().for_sport(sport_id)

    def for_channel(self, channel_id):
        return self.get_queryset().for_channel(channel_id)

    def by_type(self, event_type):
        return self.get_queryset().by_type(event_type)

    def matches(self):
        return self.get_queryset().matches()

    def races(self):
        return self.get_queryset().races()

    def simple_events(self):
        return self.get_queryset().simple_events()


class Event(models.Model):
    class EventType(models.TextChoices):
        MATCH = "match", _("Match")
        RACE = "race", _("Race")
        SIMPLE = "simple", _("Simple Event")

    event_type = models.CharField(
        max_length=10,
        choices=EventType.choices,
        db_index=True,
        editable=False,
    )
    competition = models.ForeignKey(Competition, related_name="events", on_delete=models.CASCADE)
    details = models.TextField(null=True)
    date = models.DateTimeField(db_index=True)
    channels = models.ManyToManyField(Channel, related_name="events")
    last_updated_at = models.DateTimeField(auto_now=True)

    objects = EventManager()

    class Meta:
        ordering = ["date__date", "date", "competition__sport", "competition"]

    def __str__(self):
        if self.event_type == self.EventType.MATCH:
            return f"{self.match} @ {self.competition} on {self.date}"
        if self.event_type == self.EventType.RACE:
            return f"{self.race} @ {self.competition} on {self.date}"
        return f"{self.simpleevent} @ {self.competition} on {self.date}"

    @property
    def date_end(self):
        return self.date + datetime.timedelta(hours=2)


class Match(Event):
    local = models.ForeignKey(Team, related_name="home_matches", on_delete=models.CASCADE)
    visitor = models.ForeignKey(Team, related_name="away_matches", on_delete=models.CASCADE)

    class Meta:
        unique_together = (("local", "visitor", "event_ptr"),)
        verbose_name_plural = "matches"

    def save(self, *args, **kwargs):
        self.event_type = Event.EventType.MATCH
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.local} - {self.visitor}"


class Race(Event):
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = (("name", "event_ptr"),)

    def save(self, *args, **kwargs):
        self.event_type = Event.EventType.RACE
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"


class SimpleEvent(Event):
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = (("name", "event_ptr"),)

    def save(self, *args, **kwargs):
        self.event_type = Event.EventType.SIMPLE
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"
