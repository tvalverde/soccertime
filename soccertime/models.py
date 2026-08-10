import datetime
import hashlib
import os
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.files.images import ImageFile
from django.core.validators import URLValidator
from django.db import models
from django.db.models import Count, Prefetch, Q
from django.db.models.signals import m2m_changed, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext as _

ALLOWED_LINK_SCHEMES = ["http", "https", "ftp", "ftps", "acestream", "sop", "intent", "rtmp", "m3u8"]
standard_url_validator = URLValidator(schemes=["http", "https", "ftp", "ftps"])


def validate_channel_link(value):
    if not value:
        return
    parsed = urlparse(value)
    if parsed.scheme in ALLOWED_LINK_SCHEMES:
        return
    standard_url_validator(value)


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


def gen_upload_to(instance, filename):
    return f"{instance.IMG_PARENT_DIR}/{filename[:2]}/{filename[2:4]}/{filename}"


class ImageMixin(models.Model):
    """Shared behaviour for models holding an image: content-hashed upload path and
    cached dimensions. The HTML lives in `soccertime.rendering`, not here.
    """

    IMG_PARENT_DIR = ""  # Override in subclass
    IMG_FIELD_NAME = "image"  # Override if field has different name
    IMG_WIDTH_DIVISOR = 1  # For scaling in HTML output

    class Meta:
        abstract = True

    @property
    def image_file(self):
        """The image field itself, whatever the concrete model calls it."""
        return getattr(self, self.IMG_FIELD_NAME)

    @property
    def image_dimensions(self):
        """Dimensions read from the database rather than from the file.

        `image.width` opens and parses the file on every access, which costs roughly an
        order of magnitude more than the storage lookup. `save_image` records them
        instead; rows stored before those fields existed fall back to reading the file,
        which callers must only reach after checking the file is there.

        The field deliberately does not declare `width_field` / `height_field`: that
        hooks Django's `update_dimension_fields` to `post_init`, so merely loading a row
        with unknown dimensions reads the file — and raises `FileNotFoundError` when the
        media is missing, which is the very case the placeholder exists for.
        """
        image = self.image_file
        width = getattr(self, f"{self.IMG_FIELD_NAME}_width", None)
        height = getattr(self, f"{self.IMG_FIELD_NAME}_height", None)
        if width and height:
            return width, height
        return image.width, image.height

    def save_image(self, image_bytes, original_filename):
        """Save image from bytes, using content hash as filename.

        The dimensions are measured here, from the buffer already in memory, so that
        rendering never has to open the file again.
        """
        filename = hashlib.sha1(image_bytes.getvalue()).hexdigest()
        ext = os.path.splitext(original_filename)[1]
        name = f"{filename}{ext}"
        image = ImageFile(image_bytes, name=name)
        setattr(self, f"{self.IMG_FIELD_NAME}_width", image.width)
        setattr(self, f"{self.IMG_FIELD_NAME}_height", image.height)
        self.image_file.save(name, image)
        self.save()


class Flag(ImageMixin, models.Model):
    IMG_PARENT_DIR = "flags"
    IMG_FIELD_NAME = "image"
    IMG_WIDTH_DIVISOR = 1.5

    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    image = models.ImageField(upload_to=gen_upload_to, null=True)
    image_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    image_height = models.PositiveIntegerField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

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
    def has_events(self):
        today = timezone.now().date()
        return any(event.date.date() >= today for event in self.events.all())

    @property
    def events_count(self):
        today = timezone.now().date()
        return len({event for event in self.events.all() if event.date.date() >= today})


class Team(ImageMixin, models.Model):
    IMG_PARENT_DIR = "crests"
    IMG_FIELD_NAME = "crest"
    IMG_WIDTH_DIVISOR = 1

    name = models.CharField(max_length=255, unique=True)
    crest = models.ImageField(upload_to=gen_upload_to, null=True)
    crest_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    crest_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    futbolenlatv_slug = models.SlugField(max_length=255, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_favorite_cached(self):
        return bool(self.favorite.all())

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
        if self.team and self.competition:
            return f"{self.team} @ {self.competition}"
        if self.team:
            return str(self.team)
        if self.competition:
            return self.competition.name
        return "Favorite"

    def clean(self):
        super().clean()
        if not self.competition and not self.team:
            raise ValidationError(_("At least one of competition or team must be set."))


class ChannelLinkSource(models.Model):
    name = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255, null=True, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.display_name or self.name

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.name
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_by_name(cls, name):
        return cls.objects.get_or_create(name=name, defaults={"display_name": name})


class Channel(models.Model):
    name = models.CharField(max_length=255, unique=True)
    links = models.ManyToManyField("ChannelLink", related_name="channels", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def enabled_links(self):
        return [link for link in self.links.all() if link.enabled]


# Freshest day first, and within that day the order the source listed them in: an import
# stamps `date_updated` on every row it touches, so a batch keeps the sequence the
# playlist gave it, which is usually by preference or quality. This is deliberate — do
# not collapse it to `-date_updated`, which would show every batch reversed. Defined here
# rather than inline so the channels page can group its cards and order inside them the
# same way; `verified` is a tiebreaker for when links start being checked.
CHANNEL_LINK_ORDERING = ["-date_updated__date", "date_updated__time", "-verified", "-id"]


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
    link = models.CharField(max_length=1000, null=True, blank=True, unique=True, validators=[validate_channel_link])
    sources = models.ManyToManyField("ChannelLinkSource", related_name="links", blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    enabled = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "channels links"
        ordering = CHANNEL_LINK_ORDERING

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
        ).distinct()

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

    def chronological(self):
        """Order by start time, then by sport and competition for events sharing a slot.

        The model default is a bare `date` so that counts, lookups and admin queries do
        not pay for the competition and sport JOINs; listings opt into the full order.
        """
        return self.order_by("date", "competition__sport__order", "competition__name")

    def with_related(self):
        """Preload the relations every listing walks.

        The subtype relations only exist on `Event` itself, so they are added only
        there; on `Match`, `Race` or `SimpleEvent` they would not resolve.
        """
        qs = self

        # Shared by every event
        qs = qs.select_related(
            "competition__sport",
            "competition__flag",
        ).prefetch_related(
            Prefetch("channels", queryset=Channel.objects.prefetch_related("links")),
        )

        # Subtype relations only make sense on the parent
        if self.model._meta.model_name == "event":
            qs = qs.select_related(
                "match__local",
                "match__visitor",
                "race",
                "simpleevent",
            ).prefetch_related(
                "match__local__favorite",
                "match__visitor__favorite",
                "competition__favorite",
            )

        return qs


def delete_orphan_channel_links(link_pks):
    """Delete the given links only if they no longer belong to any source."""
    if not link_pks:
        return
    ChannelLink.objects.filter(pk__in=link_pks).annotate(source_count=Count("sources")).filter(source_count=0).delete()


@receiver(pre_delete, sender=ChannelLinkSource)
def remember_links_of_deleted_source(sender, instance, **kwargs):
    # The through rows are gone by post_delete, so the candidates must be read now.
    instance._orphan_candidate_pks = list(instance.links.values_list("pk", flat=True))


@receiver(post_delete, sender=ChannelLinkSource)
def delete_orphan_channel_links_on_source_delete(sender, instance, **kwargs):
    delete_orphan_channel_links(getattr(instance, "_orphan_candidate_pks", []))


@receiver(m2m_changed, sender=ChannelLink.sources.through)
def delete_orphan_channel_links_on_m2m(sender, instance, action, reverse, pk_set, **kwargs):
    if action == "pre_clear" and reverse:
        # post_clear does not report which links were detached, so capture them first.
        instance._orphan_candidate_pks = list(instance.links.values_list("pk", flat=True))
        return

    if action not in {"post_remove", "post_clear"}:
        return

    if not reverse:
        candidate_pks = [instance.pk]
    elif action == "post_clear":
        candidate_pks = getattr(instance, "_orphan_candidate_pks", [])
    else:
        candidate_pks = list(pk_set or [])

    delete_orphan_channel_links(candidate_pks)


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
    duration = models.DurationField(
        null=True,
        blank=True,
        help_text=_("Custom duration of the event (defaults to 2 hours if not set)."),
    )
    channels = models.ManyToManyField(Channel, related_name="events")
    last_updated_at = models.DateTimeField(auto_now=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ["date"]

    @property
    def child_event(self):
        """Returns the specific child instance of this event (Match, Race, or SimpleEvent)."""
        if self.event_type == self.EventType.MATCH and hasattr(self, "match"):
            return self.match
        elif self.event_type == self.EventType.RACE and hasattr(self, "race"):
            return self.race
        elif hasattr(self, "simpleevent"):
            return self.simpleevent
        return None

    def __str__(self):
        if self.event_type == self.EventType.MATCH:
            return f"{self.match} @ {self.competition} on {self.date}"
        if self.event_type == self.EventType.RACE:
            return f"{self.race} @ {self.competition} on {self.date}"
        return f"{self.simpleevent} @ {self.competition} on {self.date}"

    @property
    def date_end(self):
        return self.date + (self.duration or datetime.timedelta(hours=2))


class Match(Event):
    local = models.ForeignKey(Team, related_name="home_matches", on_delete=models.CASCADE)
    visitor = models.ForeignKey(Team, related_name="away_matches", on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "matches"

    def save(self, *args, **kwargs):
        self.event_type = Event.EventType.MATCH
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.local} - {self.visitor}"

    @property
    def is_favorite_event(self):
        return self.local.is_favorite_cached or self.visitor.is_favorite_cached


class Race(Event):
    name = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        self.event_type = Event.EventType.RACE
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"

    @property
    def is_favorite_event(self):
        return False


class SimpleEvent(Event):
    name = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        self.event_type = Event.EventType.SIMPLE
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"

    @property
    def is_favorite_event(self):
        return False
