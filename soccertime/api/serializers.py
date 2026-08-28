"""How each record is written out.

The one rule worth stating: an image reports the dimensions the row holds and never the
ones the file holds. Reading them from the file is what returned 500 from `/competitions/`
in production, where 49 flag rows pointed at files that were no longer there — the same
reason the model fields deliberately do not declare `width_field` / `height_field`. The
URL is served whether or not the file is behind it; a client asking for a missing image
gets a 404 from the web server, which is a better answer than a 500 from here.

Two fields mirror a queryset rather than a column, and their definitions must not drift
from it: `is_favorite` marks exactly what `EventQuerySet.favorites()` selects, and
`watchable` what `watchable()` does. Both are computed in Python over relations the view
has already prefetched, so neither costs a query. `test_api_events.py` compares them
against those querysets row by row.
"""

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from soccertime.models import (
    Channel,
    ChannelLink,
    ChannelLinkSource,
    Competition,
    Event,
    Favorite,
    Flag,
    ImageMixin,
    Match,
    Race,
    SimpleEvent,
    Sport,
    Team,
)


class ImageSerializer(serializers.Serializer):
    """Where an image is and how big it is. Declared for the schema; built by `StoredImage`."""

    url = serializers.CharField(read_only=True)
    width = serializers.IntegerField(read_only=True, allow_null=True)
    height = serializers.IntegerField(read_only=True, allow_null=True)


@extend_schema_field(ImageSerializer(allow_null=True))
class StoredImage(serializers.Field):
    """The image the instance carries, or null when it was never given one.

    Takes the whole instance rather than the file, because the dimensions live beside the
    field on the model — under whatever name the concrete model gave it — and never in the
    file itself.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("source", "*")
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)

    def to_representation(self, value: ImageMixin) -> dict[str, Any] | None:
        image = value.image_file
        if not image or not image.name:
            return None
        request = self.context.get("request")
        return {
            "url": request.build_absolute_uri(image.url) if request else image.url,
            "width": getattr(value, f"{value.IMG_FIELD_NAME}_width", None),
            "height": getattr(value, f"{value.IMG_FIELD_NAME}_height", None),
        }


class SportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sport
        fields = ["id", "name", "order"]


class FlagSerializer(serializers.ModelSerializer):
    image = StoredImage()

    class Meta:
        model = Flag
        fields = ["id", "name", "display_name", "image"]


class TeamSerializer(serializers.ModelSerializer):
    crest = StoredImage()
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ["id", "name", "crest", "futbolenlatv_slug", "is_favorite"]

    def get_is_favorite(self, team: Team) -> bool:
        """Read from the prefetched rows, which is what `is_favorite_cached` exists for."""
        return team.is_favorite_cached


class CompetitionSerializer(serializers.ModelSerializer):
    sport = SportSerializer(read_only=True)
    flag = FlagSerializer(read_only=True)
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = Competition
        fields = ["id", "name", "sport", "flag", "is_favorite"]

    def get_is_favorite(self, competition: Competition) -> bool:
        """Any curated row naming it, which is the question `/competitions/` asks too."""
        return bool(competition.favorite.all())


class CompetitionDetailSerializer(CompetitionSerializer):
    """What the competitions endpoint adds: the count the site prints on each card.

    It is an annotation rather than a field, so it is only there when the queryset asked
    for it — which is why it is not on the serializer every nested competition uses.
    """

    upcoming_event_count = serializers.IntegerField(read_only=True)

    class Meta(CompetitionSerializer.Meta):
        fields = [*CompetitionSerializer.Meta.fields, "upcoming_event_count"]


class ChannelLinkSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelLinkSource
        fields = ["id", "name", "display_name", "enabled"]


class ChannelLinkSerializer(serializers.ModelSerializer):
    sources = ChannelLinkSourceSerializer(many=True, read_only=True)
    scheme = serializers.CharField(read_only=True)
    playable = serializers.BooleanField(source="has_allowed_scheme", read_only=True)
    link = serializers.SerializerMethodField()

    def get_link(self, link: ChannelLink) -> str | None:
        """The URL, unless it carries a scheme the site refuses to render.

        `link_button.html` draws nothing for those, because there escaping cannot defuse
        the value — the URL *is* the payload. Handing it out here would put it back in
        front of whoever renders this JSON, which is the same hole closed from the other
        end. The row still travels, with `playable` false and `scheme` naming what it was,
        so a caller can see that something was withheld and why.

        `save()` cannot vet a row a migration, a fixture or an `UPDATE` wrote, which is
        precisely the state production can hold and a local database cannot.
        """
        return link.link if link.has_allowed_scheme else None

    class Meta:
        model = ChannelLink
        fields = [
            "id",
            "name",
            "category",
            "subcategory",
            "quality",
            "link",
            "scheme",
            "playable",
            "enabled",
            "verified",
            "sources",
            "date_added",
            "date_updated",
        ]


class ChannelSerializer(serializers.ModelSerializer):
    links = ChannelLinkSerializer(many=True, read_only=True)

    class Meta:
        model = Channel
        fields = ["id", "name", "links"]


class FavoriteSerializer(serializers.ModelSerializer):
    """A row of the owner's curated list, which is what a visitor who chose nothing sees."""

    competition = CompetitionSerializer(read_only=True)
    team = TeamSerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ["id", "order", "competition", "team"]


class EventSerializer(serializers.ModelSerializer):
    """Every kind of event, flattened into one shape.

    `Match`, `Race` and `SimpleEvent` are separate tables joined to this one, and a client
    walking a mixed listing should not have to fetch three shapes to read it. So the fields
    only one kind has are present on all of them and null where they do not apply, and
    `title` carries what the site prints in the row whatever the kind.
    """

    competition = CompetitionSerializer(read_only=True)
    channels = ChannelSerializer(many=True, read_only=True)
    date_end = serializers.DateTimeField(read_only=True)
    title = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    local = serializers.SerializerMethodField()
    visitor = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    watchable = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "event_type",
            "title",
            "name",
            "local",
            "visitor",
            "competition",
            "date",
            "date_end",
            "duration",
            "details",
            "channels",
            "is_favorite",
            "watchable",
            "last_updated_at",
        ]

    @staticmethod
    def match_of(event: Event) -> Match | None:
        child = event.child_event
        return child if isinstance(child, Match) else None

    def get_title(self, event: Event) -> str:
        """What the row is called: the two teams, or the name of the race or event."""
        child = event.child_event
        return str(child) if child is not None else ""

    def get_name(self, event: Event) -> str | None:
        child = event.child_event
        return child.name if isinstance(child, Race | SimpleEvent) else None

    @extend_schema_field(TeamSerializer(allow_null=True))
    def get_local(self, event: Event) -> dict[str, Any] | None:
        match = self.match_of(event)
        return TeamSerializer(match.local, context=self.context).data if match else None

    @extend_schema_field(TeamSerializer(allow_null=True))
    def get_visitor(self, event: Event) -> dict[str, Any] | None:
        match = self.match_of(event)
        return TeamSerializer(match.visitor, context=self.context).data if match else None

    def get_is_favorite(self, event: Event) -> bool:
        """Exactly what `EventQuerySet.favorites()` selects, and deliberately asymmetric.

        A match counts for its teams and a race or a simple event for its competition. That
        is the curated list's own rule: starring a competition there would swamp a page meant
        to hold a handful of matches, while a race has no team to be starred by.
        """
        child = event.child_event
        if child is None:
            return False
        if isinstance(child, Match):
            return child.local.is_favorite_cached or child.visitor.is_favorite_cached
        return bool(event.competition.favorite.all())

    def get_watchable(self, event: Event) -> bool:
        """At least one enabled link, which is what a play button on the site means.

        Read over the prefetched channels rather than with a query, and enabled-only
        rather than renderable: it mirrors `EventQuerySet.watchable()`, which cannot see
        `has_allowed_scheme` because that is a Python property. Every link carries
        `playable` for a client that needs the finer answer.
        """
        return any(link.enabled for channel in event.channels.all() for link in channel.links.all())
