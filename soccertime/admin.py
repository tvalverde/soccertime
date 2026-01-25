from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin
from django.contrib.admin.templatetags.admin_urls import admin_urlname
from django.db import models
from django.db.models import Count
from django.shortcuts import resolve_url
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .filters import LinkSchemeFilter
from .models import (
    Channel,
    ChannelLink,
    ChannelLinkSource,
    Competition,
    Favorite,
    Flag,
    Match,
    Race,
    SimpleEvent,
    Sport,
    Team,
)



def escape_braces(s):
    return s.replace("{", "{{").replace("}", "}}")


def make_related_field(field):
    def display_method(obj):
        item = getattr(obj, field.name, None)
        if item is None:
            return ""
        related_model = (
            field.model
            if isinstance(field, models.OneToOneField) and field.remote_field.parent_link
            else field.related_model
        )
        url = resolve_url(admin_urlname(related_model._meta, "change"), item.id)
        return format_html('<a href="{}">{}</a>', url, item)

    display_method.short_description = f"{field.name}"
    display_method.admin_order_field = f"{field.name}"
    return display_method


class AutoModelAdmin(admin.ModelAdmin):
    list_display = []
    list_filter = []
    search_fields = []
    list_per_page = 20

    def get_list_display(self, request):
        list_display = []
        for field in self.model._meta.concrete_fields:
            if field.name == "password":
                continue
            if isinstance(field, models.OneToOneField) and field.remote_field.parent_link:
                continue
            field_name = field.name
            if field.is_relation:
                field_name = f"{field_name}_link"
                setattr(self, field_name, make_related_field(field))
            list_display.append(field_name)
        for field in self.list_display or []:
            if field not in list_display:
                list_display.append(field)
        return list_display

    def get_list_filter(self, request):
        list_filter = [field.name for field in self.model._meta.concrete_fields if field._choices]
        list_filter += [
            field.name
            for field in self.model._meta.concrete_fields
            if isinstance(field, models.DateField | models.DateTimeField)
        ]
        for field in self.list_filter or []:
            if field not in list_filter:
                list_filter.append(field)
        return list_filter

    def get_search_fields(self, request):
        search_fields = [
            field.name
            for field in self.model._meta.concrete_fields
            if isinstance(field, models.CharField | models.TextField)
        ]
        search_fields += [
            f"{field.name}__name" if hasattr(field.related_model, "name") else f"={field.name}__pk"
            for field in self.model._meta.concrete_fields
            if field.is_relation
        ]
        for field in self.search_fields or []:
            if field not in search_fields:
                search_fields.append(field)
        return search_fields


@admin.register(Sport)
class SportAdmin(SortableAdminMixin, AutoModelAdmin):
    pass


@admin.register(Competition)
class CompetitionAdmin(AutoModelAdmin):
    search_fields = ["name"]

    def get_list_filter(self, request):
        list_filter = super().get_list_filter(request)
        list_filter += [
            ("sport", admin.RelatedOnlyFieldListFilter),
        ]
        return list_filter

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        list_display[list_display.index("flag_link")] = "flag_image"
        return list_display

    @admin.display(description="flag")
    def flag_image(self, obj):
        if obj.flag:
            return mark_safe(obj.flag.flag_image())


@admin.register(Team)
class TeamAdmin(AutoModelAdmin):
    search_fields = ["name"]

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        list_display[list_display.index("crest")] = "crest_image"
        return list_display

    @admin.display(description="crest")
    def crest_image(self, obj):
        return mark_safe(obj.crest_image())


class EventModelAdmin(AutoModelAdmin):
    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        list_display.insert(list_display.index("competition_link"), "competition_sport")
        list_display.append("channels_names")
        return list_display

    def get_list_filter(self, request):
        list_filter = super().get_list_filter(request)
        list_filter += [
            ("competition__sport", admin.RelatedOnlyFieldListFilter),
        ]
        return list_filter

    def competition_sport(self, obj):
        return obj.competition.sport

    competition_sport.short_description = "sport"
    competition_sport.admin_order_field = "competition__sport"

    def channels_names(self, obj):
        return format_html_join(
            mark_safe("<br>"),
            '<a href="{}">{}</a>',
            ((resolve_url(admin_urlname(c._meta, "change"), c.pk), c.name) for c in obj.channels.all())
        )


@admin.register(Match)
class MatchAdmin(EventModelAdmin):
    date_hierarchy = "date"


@admin.register(Race)
class RaceAdmin(EventModelAdmin):
    date_hierarchy = "date"


@admin.register(SimpleEvent)
class SimpleEventAdmin(EventModelAdmin):
    date_hierarchy = "date"


class HasChannelsFilter(admin.SimpleListFilter):
    title = "Has channels"
    parameter_name = "has_channels"

    def lookups(self, request, model_admin):
        return [
            ("no", "No"),
            ("yes", "Yes"),
        ]

    def queryset(self, request, queryset):
        queryset = queryset.annotate(link_count=Count("channels__links"))
        if self.value() == "no":
            return queryset.filter(link_count=0)
        elif self.value() == "yes":
            return queryset.filter(link_count__gte=1)
        return queryset


@admin.register(ChannelLinkSource)
class ChannelLinkSourceAdmin(AutoModelAdmin):
    search_fields = ["name", "display_name"]
    list_filter = ["enabled"]


class ChannelHasLinksFilter(admin.SimpleListFilter):
    title = "Has links"
    parameter_name = "has_links"

    def lookups(self, request, model_admin):
        return [
            ("no", "No"),
            ("yes", "Yes"),
        ]

    def queryset(self, request, queryset):
        queryset = queryset.annotate(link_count=Count("links", distinct=True))
        if self.value() == "no":
            return queryset.filter(link_count=0)
        elif self.value() == "yes":
            return queryset.filter(link_count__gte=1)
        return queryset


@admin.register(Channel)
class ChannelAdmin(AutoModelAdmin):
    search_fields = ["name"]
    filter_horizontal = ["links"]
    list_filter = [ChannelHasLinksFilter]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(link_count=Count("links", distinct=True))

    @admin.display(ordering="link_count", description="links")
    def links_count(self, obj):
        return obj.link_count

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if "links_count" not in list_display:
            list_display.append("links_count")
        return list_display




@admin.register(ChannelLink)
class ChannelLinkAdmin(AutoModelAdmin):
    list_filter = [HasChannelsFilter, LinkSchemeFilter, "verified", "sources__name"]
    filter_horizontal = ["sources"]
    search_fields = ["name", "link", "sources__name"]



@admin.register(Favorite)
class FavoriteAdmin(SortableAdminMixin, AutoModelAdmin):
    autocomplete_fields = ["competition", "team"]

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        list_display.insert(list_display.index("_reorder_"), "crest_image")
        return list_display

    @admin.display(description="crest")
    def crest_image(self, obj):
        if obj.team:
            return mark_safe(obj.team.crest_image())


@admin.register(Flag)
class FlagAdmin(AutoModelAdmin):
    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        list_display[list_display.index("image")] = "flag_image"
        return list_display

    @admin.display(description="image")
    def flag_image(self, obj):
        return mark_safe(obj.flag_image())
