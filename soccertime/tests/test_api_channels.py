"""Channels, the links they carry, and where those links came from.

The one property worth more than the field lists: a link the site refuses to render must
not be offered as playable here either. `ChannelLink.save` vets the scheme on the way in,
but a row written by a migration, a fixture or a hand-written `UPDATE` never passed
through it — which is exactly the state production can hold and a local database cannot,
so these tests write one that way on purpose.
"""

import pytest
from django.urls import reverse

from soccertime.models import ChannelLink


def results(response):
    return response.json()["results"]


def names(response):
    return [row["name"] for row in results(response)]


def store_raw_link(link, value):
    """Put a value in the column the way everything except `save()` does."""
    ChannelLink.objects.filter(pk=link.pk).update(link=value)


@pytest.mark.django_db
class TestChannels:
    def test_a_channel_carries_the_links_it_holds(self, client, channel_with_links):
        payload = client.get(reverse("channel-detail", args=[channel_with_links.pk])).json()

        assert payload["name"] == "Movistar LaLiga"
        assert {link["name"] for link in payload["links"]} == {"Movistar LaLiga HD", "Movistar LaLiga SD"}

    def test_a_channel_without_links_carries_an_empty_list(self, client, channel_dazn):
        payload = client.get(reverse("channel-detail", args=[channel_dazn.pk])).json()

        assert payload["links"] == []

    def test_each_link_says_whether_it_is_enabled(self, client, channel_with_links):
        payload = client.get(reverse("channel-detail", args=[channel_with_links.pk])).json()
        enabled = {link["name"]: link["enabled"] for link in payload["links"]}

        assert enabled == {"Movistar LaLiga HD": True, "Movistar LaLiga SD": False}

    def test_filtering_by_having_something_to_play(self, client, channel_with_links, channel_dazn):
        response = client.get(reverse("channel-list"), {"has_enabled_links": "true"})

        assert names(response) == ["Movistar LaLiga"]

    def test_searching_by_name(self, client, channels):
        assert names(client.get(reverse("channel-list"), {"search": "dazn"})) == ["DAZN"]

    def test_the_listing_is_alphabetical(self, client, channels):
        assert names(client.get(reverse("channel-list"))) == ["DAZN", "Movistar LaLiga"]


@pytest.mark.django_db
class TestChannelLinks:
    def test_a_link_carries_what_the_directory_shows(self, client, channel_link):
        payload = client.get(reverse("channel-link-detail", args=[channel_link.pk])).json()

        assert payload["name"] == "Movistar LaLiga HD"
        assert payload["category"] == "Deportes"
        assert payload["subcategory"] == "Fútbol"
        assert payload["quality"] == "HD"
        assert payload["link"] == "https://example.com/stream1"
        assert payload["enabled"] is True
        assert payload["verified"] is False

    def test_a_link_names_its_scheme(self, client, channel_link):
        payload = client.get(reverse("channel-link-detail", args=[channel_link.pk])).json()

        assert payload["scheme"] == "https"

    def test_a_link_names_the_sources_that_carry_it(self, client, channel_link):
        payload = client.get(reverse("channel-link-detail", args=[channel_link.pk])).json()

        assert [source["name"] for source in payload["sources"]] == ["test"]

    def test_a_playable_link_says_so(self, client, channel_link):
        assert client.get(reverse("channel-link-detail", args=[channel_link.pk])).json()["playable"] is True

    def test_a_link_the_site_would_refuse_to_render_is_not_playable(self, client, channel_link):
        """`save()` cannot vet a row written by an `UPDATE`, a migration or a fixture."""
        store_raw_link(channel_link, "javascript:alert(1)")

        payload = client.get(reverse("channel-link-detail", args=[channel_link.pk])).json()

        assert payload["playable"] is False

    def test_the_playable_filter_leaves_it_out(self, client, channel_link, channel_link_disabled):
        store_raw_link(channel_link, "javascript:alert(1)")

        assert names(client.get(reverse("channel-link-list"), {"playable": "true"})) == ["Movistar LaLiga SD"]

    def test_the_playable_filter_agrees_with_what_the_site_renders(self, client, channel_link):
        """The filter runs in the database and the property in Python; they must not drift."""
        store_raw_link(channel_link, "acestream://abc123")

        playable_here = {row["id"] for row in results(client.get(reverse("channel-link-list"), {"playable": "true"}))}
        playable_there = {link.pk for link in ChannelLink.objects.all() if link.has_allowed_scheme}

        assert playable_here == playable_there

    def test_a_link_the_site_would_refuse_to_render_is_not_handed_out(self, client, channel_link):
        """The URL is the payload for those schemes, so escaping cannot defuse it.

        `link_button.html` draws nothing for them. Serving the value here would put it in
        front of whoever renders this JSON instead — the same hole, one layer further out.
        """
        store_raw_link(channel_link, "javascript:alert(1)")

        payload = client.get(reverse("channel-link-detail", args=[channel_link.pk])).json()

        assert payload["link"] is None
        assert payload["playable"] is False
        assert payload["scheme"] == "javascript"

    def test_a_withheld_link_is_still_listed(self, client, channel_link):
        """The row travels, so a count or a filter is not quietly wrong about what exists."""
        store_raw_link(channel_link, "javascript:alert(1)")

        assert names(client.get(reverse("channel-link-list"))) == ["Movistar LaLiga HD"]

    def test_the_channels_listing_withholds_it_too(self, client, channel_with_links, channel_link):
        """The same rule wherever a link is nested, not only where it is the resource."""
        store_raw_link(channel_link, "javascript:alert(1)")

        payload = client.get(reverse("channel-detail", args=[channel_with_links.pk])).json()
        withheld = [link for link in payload["links"] if link["name"] == "Movistar LaLiga HD"]

        assert withheld[0]["link"] is None

    def test_filtering_by_enabled(self, client, channel_link, channel_link_disabled):
        assert names(client.get(reverse("channel-link-list"), {"enabled": "true"})) == ["Movistar LaLiga HD"]

    def test_filtering_by_disabled(self, client, channel_link, channel_link_disabled):
        """A field the database holds answers both ways, unlike a derived flag."""
        assert names(client.get(reverse("channel-link-list"), {"enabled": "false"})) == ["Movistar LaLiga SD"]

    def test_filtering_by_quality(self, client, channel_link, channel_link_disabled):
        assert names(client.get(reverse("channel-link-list"), {"quality": "SD"})) == ["Movistar LaLiga SD"]

    def test_an_unknown_quality_is_refused(self, client):
        assert client.get(reverse("channel-link-list"), {"quality": "4K"}).status_code == 400

    def test_filtering_by_category(self, client, channel_link):
        assert len(names(client.get(reverse("channel-link-list"), {"category": "Deportes"}))) == 1
        assert names(client.get(reverse("channel-link-list"), {"category": "Cine"})) == []

    def test_filtering_by_source(self, client, channel_link, channel_link_source):
        response = client.get(reverse("channel-link-list"), {"source": channel_link_source.pk})

        assert names(response) == ["Movistar LaLiga HD"]

    def test_searching_by_name(self, client, channel_link, channel_link_disabled):
        assert names(client.get(reverse("channel-link-list"), {"search": "hd"})) == ["Movistar LaLiga HD"]

    def test_the_listing_keeps_the_order_the_directory_uses(self, client, channel_link, channel_link_disabled):
        """Freshest day first, then the sequence the source listed them in."""
        listed = [row["id"] for row in results(client.get(reverse("channel-link-list")))]

        assert listed == [link.pk for link in ChannelLink.objects.all()]


@pytest.mark.django_db
class TestChannelLinkSources:
    def test_a_source_carries_both_of_its_names_and_its_state(self, client, channel_link_source):
        payload = client.get(reverse("channel-link-source-detail", args=[channel_link_source.pk])).json()

        assert payload == {
            "id": channel_link_source.pk,
            "name": "test",
            "display_name": "test",
            "enabled": True,
        }

    def test_filtering_by_enabled(self, client, channel_link_source):
        channel_link_source.enabled = False
        channel_link_source.save()

        assert names(client.get(reverse("channel-link-source-list"), {"enabled": "true"})) == []
        assert names(client.get(reverse("channel-link-source-list"), {"enabled": "false"})) == ["test"]
