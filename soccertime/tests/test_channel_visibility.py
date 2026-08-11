"""What the agenda's channel column shows, and which events count as watchable.

`channels_list.html` used to render a channel **only if it had an enabled link**, and drop
every other one — except under `DEBUG`, where they appeared struck through, so the one reader
who ever saw them was a developer. In production the column was simply empty: a page fetched
on 2026-08-11 had 25 rows, 8 showing a channel, 17 blank, and the 8 were exactly the 8 with a
play button.

The site was therefore discarding what it had been told. Of 2,148 future events, 339 were
watchable and shown, **952 named a real channel that was hidden** — HBO MAX, DAZN, Movistar+ —
and 857 carried only the `Canal por confirmar` placeholder. A television agenda that knows
where a match is on and does not say so is failing at its one job.

Nothing asserted what that column contained, which is why it could be this wrong for this
long.
"""

import datetime

import pytest
from django.template.loader import render_to_string
from django.utils import timezone

from soccertime.models import Channel, ChannelLink, Event, Match

WATCHABLE = "acestream://a1b2c3"


def channel_cell(event):
    """The channels column alone, so an assertion cannot pass on markup from another cell."""
    return render_to_string("soccertime/channels_list.html", {"event": event})


def row(parent_event):
    """A whole agenda row, built the way `agenda.html` builds it: child inside, parent outside."""
    return render_to_string(
        "soccertime/agenda_item.html",
        {"event": parent_event.child_event, "parent_event": parent_event},
    )


@pytest.fixture
def event_on(db, competition, team_home, team_away):
    """A match carrying the given channels, read back as a view would see it."""

    def build(*channels):
        match = Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=timezone.now() + datetime.timedelta(hours=3),
        )
        match.channels.set(channels)
        return Event.objects.prefetch_related("channels__links").get(pk=match.pk)

    return build


@pytest.fixture
def channel(db):
    def build(name, link=None, *, enabled=True):
        channel = Channel.objects.create(name=name)
        if link is not None:
            channel.links.add(ChannelLink.objects.create(name=f"{name} link", link=link, enabled=enabled))
        return channel

    return build


class TestTheChannelColumn:
    def test_it_names_a_channel_that_has_no_link(self, event_on, channel):
        """The 952 events the site knew about and said nothing for."""
        cell = channel_cell(event_on(channel("DAZN")))

        assert "DAZN" in cell

    def test_a_channel_without_a_link_gets_no_play_button(self, event_on, channel):
        """Naming it must not imply it can be watched."""
        cell = channel_cell(event_on(channel("DAZN")))

        assert "bi-play-circle-fill" not in cell

    def test_a_channel_with_a_link_keeps_its_play_button(self, event_on, channel):
        cell = channel_cell(event_on(channel("Movistar", WATCHABLE)))

        assert "Movistar" in cell
        assert "bi-play-circle-fill" in cell

    def test_the_two_are_told_apart(self, event_on, channel):
        """Shown is not enough: the difference has to be visible before clicking."""
        watchable = channel_cell(event_on(channel("Movistar", WATCHABLE)))
        listed_only = channel_cell(event_on(channel("DAZN")))

        assert "channel-unlinked" in listed_only
        assert "channel-unlinked" not in watchable

    def test_the_placeholder_is_shown_like_any_other_channel(self, event_on, channel):
        """`Canal por confirmar` is 857 future events, and is not special-cased anywhere.

        An empty cell is ambiguous — nothing on, or nothing known? Naming it answers that, and
        keeping it an ordinary `Channel` row keeps a Spanish string out of the template.
        """
        cell = channel_cell(event_on(channel("Canal por confirmar")))

        assert "Canal por confirmar" in cell
        assert "channel-unlinked" in cell

    def test_only_the_badge_is_muted_never_the_row(self, event_on, channel):
        """The page is the agenda first.

        The time, the teams and the competition keep their contrast whether or not anything can
        be watched — dimming the row would trade one failure for a worse one.
        """
        markup = row(event_on(channel("DAZN")))
        before_channels, _, channels = markup.partition('<td class="lh-lg">')

        assert channels, "the channels cell moved; this test is asserting nothing"
        assert "channel-unlinked" not in before_channels
        assert "channel-unlinked" in channels
        assert markup.count("channel-unlinked") == 1


class TestTheOrderInsideARow:
    """What can be played comes before what can only be known.

    `Channel.Meta.ordering` is alphabetical, so a row on ATP Tennis TV and Movistar Plus+ put
    the one without a link first and hid the play buttons behind it.
    """

    def test_a_playable_channel_comes_before_one_without_a_link(self, event_on, channel):
        # Alphabetically the linkless one wins, so the sort has to be doing the work.
        event = event_on(channel("AAA sin enlace"), channel("ZZZ con enlace", WATCHABLE))

        cell = channel_cell(event)

        assert cell.index("ZZZ con enlace") < cell.index("AAA sin enlace")

    def test_it_costs_no_query(self, event_on, channel, django_assert_num_queries):
        """Sorted over what `with_related()` already prefetched, not fetched again."""
        event = event_on(channel("Uno", WATCHABLE), channel("Dos"))

        with django_assert_num_queries(0):
            assert [c.name for c in event.channels_by_availability] == ["Uno", "Dos"]


class TestWatchable:
    def test_it_keeps_an_event_with_an_enabled_link(self, event_on, channel):
        event = event_on(channel("Movistar", WATCHABLE))

        assert event.pk in set(Event.objects.watchable().values_list("pk", flat=True))

    def test_it_drops_an_event_whose_channel_has_no_link(self, event_on, channel):
        event = event_on(channel("DAZN"))

        assert event.pk not in set(Event.objects.watchable().values_list("pk", flat=True))

    def test_it_drops_an_event_whose_link_is_disabled(self, event_on, channel):
        event = event_on(channel("Apagado", "acestream://off", enabled=False))

        assert event.pk not in set(Event.objects.watchable().values_list("pk", flat=True))

    def test_an_event_on_two_watchable_channels_appears_once(self, event_on, channel):
        """The many-to-many hazard that kept channel out of `search()` in 0.4.2.

        Without `distinct()` the join multiplies the row, and the duplicate would land inside
        the pagination added the same day.
        """
        event = event_on(channel("Uno", "acestream://uno"), channel("Dos", "acestream://dos"))

        assert list(Event.objects.watchable().values_list("pk", flat=True)).count(event.pk) == 1


class TestTheFilterAgreesWithThePage:
    def test_a_link_the_template_refuses_to_render_is_still_counted(self, event_on, channel):
        """A seam left open on purpose, pinned here so it cannot surprise anyone.

        `has_allowed_scheme` is a Python property, so the SQL filter cannot see it: a link that
        is enabled but carries a scheme the template will not render counts as watchable and
        then draws no play button. Measured against production the two agree exactly — 339 by
        SQL, 339 by what the template draws — because all 381 enabled links are `acestream`.
        This documents what happens on the day one is not.
        """
        event = event_on(channel("Raro", "acestream://placeholder"))
        # Written under the model, because `save()` vets the scheme since 0.4.1 — which is
        # precisely the docstring's point: only a migration, a fixture or a hand-written
        # UPDATE can put such a row in the table, and this is one. Re-read afterwards: the
        # prefetched instance still holds the value it was created with.
        ChannelLink.objects.filter(name="Raro link").update(link="mailto:someone@example.com")
        event = Event.objects.prefetch_related("channels__links").get(pk=event.pk)

        assert event.pk in set(Event.objects.watchable().values_list("pk", flat=True))
        assert "bi-play-circle-fill" not in channel_cell(event)


@pytest.mark.django_db
class TestTheAgendaFilter:
    """`?watchable=1`, one identifier because `{% querystring %}` cannot take a hyphen, and
    English like the `events-date`, `search` and `page` beside it."""

    def test_it_narrows_the_listing_to_what_can_be_watched(self, client, event_on, channel):
        watchable = event_on(channel("Movistar", WATCHABLE))
        listed_only = event_on(channel("DAZN"))

        body = client.get("/agenda/", {"watchable": "1"}).content.decode()

        assert str(watchable.competition) in body
        assert "DAZN" not in body
        assert listed_only.pk not in {e.pk for e in client.get("/agenda/", {"watchable": "1"}).context["events"]}

    def test_without_the_parameter_everything_is_listed(self, client, event_on, channel):
        listed_only = event_on(channel("DAZN"))

        page = client.get("/agenda/").context["events"]

        assert listed_only.pk in {e.pk for e in page}

    def test_it_composes_with_a_search_without_duplicating_rows(self, client, event_on, channel, team_home):
        """Two filters over the same many-to-many join is where a missing `distinct()` shows."""
        event = event_on(channel("Uno", "acestream://uno"), channel("Dos", "acestream://dos"))

        page = client.get("/agenda/", {"watchable": "1", "search": team_home.name}).context["events"]

        assert [e.pk for e in page].count(event.pk) == 1

    def test_the_counts_describe_the_list_underneath_them(self, client, event_on, channel):
        event_on(channel("Movistar", WATCHABLE))
        event_on(channel("DAZN"))
        event_on(channel("Canal por confirmar"))

        response = client.get("/agenda/")

        assert response.context["total_events"] == 3
        assert response.context["watchable_events"] == 1

    def test_the_counts_are_scoped_to_the_search(self, client, event_on, channel, team_home):
        """A count that ignored the current filter would contradict the rows below it."""
        event_on(channel("Movistar", WATCHABLE))

        response = client.get("/agenda/", {"search": "no-existe-nada-asi"})

        assert response.context["total_events"] == 0
        assert response.context["watchable_events"] == 0

    def test_the_filtered_page_says_why_it_is_empty(self, client, event_on, channel):
        event_on(channel("DAZN"))

        response = client.get("/agenda/", {"watchable": "1"})

        assert "enlace" in response.context["empty_message"].lower()
