"""The pagination control, and the query string it has to carry with it.

`{% bootstrap_pagination %}` built every link as a bare `?page=N`, so following page two of
a search returned the whole unfiltered agenda instead — silently, since the page looks
perfectly normal, just with the wrong rows. Against production: `/agenda/?search=Real`
listed 33 rows, its own page-two link went to `/agenda/?page=2` and served 27 rows of
everything, while `/agenda/?search=Real&page=2` had the 43 that were actually wanted.

The tag could not be told otherwise: in 26.1 it accepts `pages_to_show`, `url`, `size` and
`justify_content`, and nothing for the rest of the parameters. So it was replaced by a
partial built on `{% querystring %}`, and the first test here is that bug.
"""

import datetime

import pytest
from bs4 import BeautifulSoup
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from soccertime.models import Competition, Match, Sport, Team

PER_PAGE = 25


def make_events(count, competition, home):
    """Enough events to paginate, each against a differently named opponent."""
    for index in range(count):
        Match.objects.create(
            competition=competition,
            local=home,
            visitor=Team.objects.create(name=f"Rival {index}"),
            date=timezone.now() + datetime.timedelta(hours=index + 1),
        )


@pytest.fixture
def many_events(db):
    sport = Sport.objects.create(name="Fútbol", order=1)
    competition = Competition.objects.create(name="Liga Buscable", sport=sport)
    make_events(PER_PAGE * 3, competition, Team.objects.create(name="Equipo Buscable"))
    return competition


def page_links(response):
    soup = BeautifulSoup(response.content, "html.parser")
    return [a["href"] for a in soup.select("nav .pagination a.page-link")]


def page_items(response):
    soup = BeautifulSoup(response.content, "html.parser")
    return soup.select("nav .pagination li")


@pytest.mark.django_db
class TestTheSearchSurvivesPaging:
    """The bug this replaced the widget for."""

    def test_every_page_link_carries_the_search(self, client, many_events):
        response = client.get(reverse("agenda"), {"search": "Buscable"})

        links = page_links(response)
        assert links
        assert all("search=Buscable" in link for link in links)

    def test_following_a_page_link_stays_filtered(self, client, many_events):
        """The whole point: page two of a search is still the search."""
        first = client.get(reverse("agenda"), {"search": "Buscable"})
        second_page = next(link for link in page_links(first) if "page=2" in link)

        response = client.get(reverse("agenda") + second_page.replace("&amp;", "&"))

        assert response.context["events"].number == 2
        assert response.context["events"].paginator.count == PER_PAGE * 3

    def test_paging_without_a_search_is_unaffected(self, client, many_events):
        response = client.get(reverse("agenda"))

        assert all(link.startswith("?page=") for link in page_links(response))


@pytest.mark.django_db
class TestTheControlItself:
    def test_previous_is_disabled_on_the_first_page(self, client, many_events):
        items = page_items(client.get(reverse("agenda")))

        assert "disabled" in items[0].get("class")
        assert not items[0].find("a")

    def test_next_is_disabled_on_the_last_page(self, client, many_events):
        items = page_items(client.get(reverse("agenda"), {"page": 3}))

        assert "disabled" in items[-1].get("class")
        assert not items[-1].find("a")

    def test_the_current_page_is_marked_and_not_a_link(self, client, many_events):
        response = client.get(reverse("agenda"), {"page": 2})

        (active,) = [item for item in page_items(response) if "active" in (item.get("class") or [])]
        assert active.get("aria-current") == "page"
        assert active.get_text(strip=True) == "2"
        assert not active.find("a")

    def test_the_other_pages_are_links(self, client, many_events):
        links = page_links(client.get(reverse("agenda"), {"page": 2}))

        assert "?page=1" in links
        assert "?page=3" in links

    def test_nothing_is_rendered_for_a_single_page(self, client, db, competition, team_home, team_away):
        """One page of results needs no control at all."""
        Match.objects.create(
            competition=competition,
            local=team_home,
            visitor=team_away,
            date=timezone.now() + datetime.timedelta(hours=1),
        )

        assert b"pagination" not in client.get(reverse("agenda")).content

    def test_a_view_that_does_not_paginate_renders_nothing(self, client, db, match, team_home):
        """Four of the six views on this template pass a queryset with no page at all."""
        response = client.get(reverse("team-events", args=[team_home.pk]))

        assert b"pagination" not in response.content


@pytest.mark.django_db
class TestTheGapsBetweenPages:
    def test_an_ellipsis_appears_when_there_are_many_pages(self, client, db):
        sport = Sport.objects.create(name="Fútbol", order=1)
        competition = Competition.objects.create(name="Larga", sport=sport)
        make_events(PER_PAGE * 12, competition, Team.objects.create(name="Local"))

        text = client.get(reverse("agenda"), {"page": 6}).content.decode()

        assert "..." in text
        assert "?page=1" in text and "?page=12" in text

    def test_no_ellipsis_when_every_page_fits(self, client, many_events):
        items = page_items(client.get(reverse("agenda")))

        assert not any(item.get_text(strip=True) == "..." for item in items)


def test_django_bootstrap5_is_gone():
    """It supported one live tag, and that tag was the bug above."""
    assert "django_bootstrap5" not in settings.INSTALLED_APPS
