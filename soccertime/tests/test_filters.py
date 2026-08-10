"""Tests for the admin list filters."""

import pytest
from django.contrib import admin

from soccertime.admin import ChannelLinkAdmin
from soccertime.filters import LinkSchemeFilter
from soccertime.models import ChannelLink


@pytest.fixture
def links(db, channel_link_source):
    for name, url in (
        ("Acestream", "acestream://" + "a" * 40),
        ("Web", "https://example.com/stream"),
        ("Plain", "http://example.com/stream"),
        ("Pending", None),
    ):
        link = ChannelLink.objects.create(name=name, link=url)
        link.sources.add(channel_link_source)


def build_filter(value=None):
    params = {LinkSchemeFilter.parameter_name: [value]} if value else {}
    return LinkSchemeFilter(None, params, ChannelLink, ChannelLinkAdmin(ChannelLink, admin.site))


def schemes_offered():
    return {scheme for scheme, _ in build_filter().lookups(None, ChannelLinkAdmin(ChannelLink, admin.site))}


def filtered_names(value=None):
    return [link.name for link in build_filter(value).queryset(None, ChannelLink.objects.all())]


@pytest.mark.django_db
class TestLinkSchemeFilter:
    def test_lists_every_scheme_in_use(self, links):
        assert schemes_offered() == {"acestream", "https", "http"}

    def test_ignores_rows_without_a_link(self, links):
        """A pending row has no scheme and must not produce an empty option."""
        assert all(schemes_offered())

    def test_filters_by_the_selected_scheme(self, links):
        assert filtered_names("acestream") == ["Acestream"]

    def test_returns_everything_when_nothing_is_selected(self, links):
        assert len(filtered_names()) == 4

    def test_http_does_not_swallow_https(self, links):
        """Matching on the bare prefix would return both."""
        assert filtered_names("http") == ["Plain"]

    def test_no_links_at_all(self, db):
        assert schemes_offered() == set()
