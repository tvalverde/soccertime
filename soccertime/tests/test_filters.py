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
    """What the admin renders: SimpleListFilter resolves the choices when constructed."""
    return [scheme for scheme, _ in build_filter().lookup_choices]


def filtered_names(value=None):
    return [link.name for link in build_filter(value).queryset(None, ChannelLink.objects.all())]


@pytest.mark.django_db
class TestLinkSchemeFilter:
    def test_lists_every_scheme_in_use(self, links):
        assert set(schemes_offered()) == {"acestream", "https", "http"}

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

    def test_lists_them_in_a_stable_order(self, links):
        """They came out of a set, so the dropdown order changed between processes."""
        assert schemes_offered() == sorted(schemes_offered())
        assert schemes_offered() == ["acestream", "http", "https"]

    def test_resolves_the_schemes_in_a_single_query(self, links, django_assert_num_queries):
        """It used to read every row into Python to parse it."""
        with django_assert_num_queries(1):
            build_filter()

    def test_ignores_links_with_no_scheme(self, db, channel_link_source):
        """Such a row can no longer be saved, but the filter must still tolerate one.

        `ChannelLink.save()` rejects a link whose scheme is not on the allowlist, and a
        bare string has no scheme at all. `bulk_create` goes straight to SQL without
        calling `save()`, which is how a legacy row — or a migration, or a fixture —
        can still put one in the table.
        """
        (link,) = ChannelLink.objects.bulk_create([ChannelLink(name="Bare", link="just-a-hash")])
        link.sources.add(channel_link_source)

        assert schemes_offered() == []

    def test_no_links_at_all(self, db):
        assert schemes_offered() == []
