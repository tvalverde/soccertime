"""Favourites belonging to the visitor rather than to the owner.

They were curated in the admin and every visitor saw the same ones, so the landing page was
one person's agenda. Each visitor picks their own now, and the whole difficulty is that every
public page is cached for an hour and served to everybody: whatever tells one visitor from
another has to travel in the request, or the page of one is handed to the other.

It travels in a signed cookie and the **server** does the filtering, which is what lets the
page paginate. Filtering in the browser instead was tried and abandoned: the server would
have had to ship the whole window for a script to sift — 437.1 KB against 36.6 KB, measured
on a copy of the production database — and pagination becomes impossible, because the server
would be paginating events the visitor never asked for and their own could land on page three
while the first looked empty.

Three properties are worth more than the feature itself, and each has its own class below:
nobody without a cookie sees anything different from before; nobody with one is ever served
somebody else's page; and no page carrying a CSRF token is in the shared cache, because
rendering one makes Django set a `csrftoken` cookie and a cached copy would hand the same
token and the same cookie to every other visitor.
"""

import datetime
import re

import pytest
from bs4 import BeautifulSoup
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from soccertime.models import Competition, Favorite, Match, Team
from soccertime.visitor_favorites import COOKIE_NAME, MAX_PER_KIND, Selection

CACHED_PAGES = ["favorites", "agenda", "competitions", "channels"]


@pytest.fixture
def server_side_cache(settings):
    """The real thing rather than the dummy backend the suite runs with."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.CACHE_PAGE_TIMEOUT = 3600
    from django.core.cache import caches

    caches["default"].clear()
    return caches["default"]


@pytest.fixture
def visitor(db):
    """A browser of its own, so two of them cannot share a cookie jar."""
    return Client()


def star(client, kind, entity):
    return client.post(reverse(f"toggle-favorite-{kind}", args=[entity.pk]))


def listed_teams(html):
    """The teams named in the rows of a listing, which is what identifies what it shows."""
    soup = BeautifulSoup(html, "html.parser")
    return {link.get_text(strip=True) for link in soup.select('a[href*="/events/team/"]')}


def event_rows(html):
    return BeautifulSoup(html, "html.parser").select("tr[data-starts-at]")


def _linked_ids(elements, kind):
    return {int(re.search(rf"/{kind}/(\d+)/", element["href"]).group(1)) for element in elements}


def strip_competition_ids(html):
    """The flag strip that sits above every listing."""
    strip = BeautifulSoup(html, "html.parser").select_one("div.bg-primary")
    return _linked_ids(strip.select("a"), "competition") if strip else set()


def strip_team_ids(html):
    """The crest strip, which only the agenda carries."""
    strip = BeautifulSoup(html, "html.parser").select_one("#teams-container")
    return _linked_ids(strip.select("a"), "team") if strip else set()


def highlighted_competition_ids(html):
    """The competitions the listing page marks as favourites."""
    marked = BeautifulSoup(html, "html.parser").select("a.text-bg-warning")
    return _linked_ids(marked, "competition")


def bordered_rows(html):
    return BeautifulSoup(html, "html.parser").select("tr.favorite-event")


@pytest.fixture
def crested_team(db):
    """The strip skips teams with no crest, so a team that appears in it needs one.

    The file does not have to exist — `image_markup` draws its placeholder when it is
    missing — and this is about which teams the strip lists, not what they look like.
    """
    return Team.objects.create(name="Girona FC", crest="crests/girona.png")


@pytest.fixture
def other_match(db, competition_champions):
    """A match the owner never curated, between two teams nothing else in here features.

    Its own teams on purpose: sharing one with the curated match would make a test pass or
    fail for a reason that has nothing to do with what it claims to be about.
    """
    return Match.objects.create(
        competition=competition_champions,
        local=Team.objects.create(name="Girona"),
        visitor=Team.objects.create(name="Rayo Vallecano"),
        date=timezone.now() + datetime.timedelta(hours=5),
    )


@pytest.mark.django_db
class TestNothingChangesForSomebodyWhoChoosesNothing:
    """The promise this work made. Every crawler and every first visit is in this class."""

    def test_the_landing_page_is_still_the_owner_s_favourites(self, client, match, other_match, favorite_team):
        html = client.get(reverse("favorites")).content.decode()

        assert listed_teams(html) == {match.local.name, match.visitor.name}

    def test_and_is_still_served_from_the_shared_cache(
        self, client, match, favorite_team, server_side_cache, django_assert_num_queries
    ):
        client.get(reverse("favorites"))

        with django_assert_num_queries(0):
            client.get(reverse("favorites"))

    def test_a_cookie_from_somewhere_else_does_not_take_them_off_it(
        self, client, match, favorite_team, server_side_cache, django_assert_num_queries
    ):
        """Only this site's own cookie means anything; anything else still gets the cached page."""
        client.get(reverse("favorites"))
        client.cookies["something_else"] = "value"

        with django_assert_num_queries(0):
            client.get(reverse("favorites"))

    @pytest.mark.parametrize("page", ["favorites", "agenda", "competitions"])
    def test_an_unsigned_cookie_cannot_switch_the_cache_off(
        self, client, page, match, favorite_team, server_side_cache, django_assert_num_queries
    ):
        """What made this worth a test: the branch used to be on the cookie's *name*.

        `Cookie: soccertime_favorites=x` carries no signature, so the page rendered was the
        ordinary curated one — but rendered again on every request, with no rate limit in
        front of it. Measured at 1.9-2.3s each on `/competitions/` against production data,
        which is half a request per second to saturate the container that also serves the
        database. The signature is what decides now.
        """
        client.get(reverse(page))
        client.cookies[COOKIE_NAME] = "not-signed-by-this-site"

        with django_assert_num_queries(0):
            client.get(reverse(page))


@pytest.mark.django_db
class TestAVisitorSeesTheirOwn:
    def test_starring_a_team_puts_its_matches_on_the_landing_page(self, visitor, match, other_match, favorite_team):
        star(visitor, "team", other_match.local)

        html = visitor.get(reverse("favorites")).content.decode()

        assert listed_teams(html) == {other_match.local.name, other_match.visitor.name}

    def test_and_takes_the_owner_s_off_it(self, visitor, match, other_match, favorite_team):
        star(visitor, "team", other_match.local)

        html = visitor.get(reverse("favorites")).content.decode()

        assert match.local.name not in listed_teams(html)

    def test_starring_a_competition_brings_its_matches(self, visitor, match, favorite_team):
        """Where this parts company with the curated rule, which counts a competition only for
        races and simple events. Somebody who pressed the star on La Liga's own page means its
        matches, and the listing paginates, so a broad choice costs pages rather than a page."""
        star(visitor, "competition", match.competition)

        html = visitor.get(reverse("favorites")).content.decode()

        assert listed_teams(html) == {match.local.name, match.visitor.name}

    def test_pressing_the_star_again_removes_it(self, visitor, match, other_match, favorite_team):
        star(visitor, "team", other_match.local)
        star(visitor, "team", other_match.local)

        html = visitor.get(reverse("favorites")).content.decode()

        assert event_rows(html) == []

    def test_removing_the_last_one_shows_an_empty_agenda_not_the_owner_s(
        self, visitor, match, other_match, favorite_team
    ):
        """Empty is a choice. Falling back to the curated list here would make the owner's
        favourites impossible to get rid of."""
        star(visitor, "team", other_match.local)
        star(visitor, "team", other_match.local)

        html = visitor.get(reverse("favorites")).content.decode()

        assert "No hay eventos" in html

    def test_the_landing_page_paginates(self, visitor, competition, team_home):
        """Thirty matches in one competition, one star, and the page still holds twenty-five.

        This is what filtering on the server buys. A page that shipped the whole window for a
        script to sift could not paginate at all: the server would be counting events the
        visitor never chose, so page one could come back empty.
        """
        for index in range(30):
            Match.objects.create(
                competition=competition,
                local=team_home,
                visitor=Team.objects.create(name=f"Rival {index}"),
                date=timezone.now() + datetime.timedelta(hours=2, minutes=index),
            )
        star(visitor, "competition", competition)

        html = visitor.get(reverse("favorites")).content.decode()

        assert len(event_rows(html)) == 25

    def test_their_page_is_not_put_in_the_shared_cache(
        self, visitor, match, other_match, favorite_team, server_side_cache
    ):
        """It would be served to the next visitor, which is the whole hazard this avoids."""
        star(visitor, "team", other_match.local)
        visitor.get(reverse("favorites"))

        stranger = Client()
        html = stranger.get(reverse("favorites")).content.decode()

        assert listed_teams(html) == {match.local.name, match.visitor.name}

    def test_pressing_a_star_does_not_clear_the_shared_cache(
        self, visitor, match, favorite_team, server_side_cache, django_assert_num_queries
    ):
        """A visitor's choice is their own business and costs everybody else nothing.

        Clearing the shared cache on a star would hand any stranger a way to make every page
        on the site re-render as often as they liked. Only the owner's own `Favorite` rows
        clear it, and those can only be changed from the admin.
        """
        stranger = Client()
        stranger.get(reverse("favorites"))

        star(visitor, "team", match.local)

        with django_assert_num_queries(0):
            stranger.get(reverse("favorites"))

    def test_two_visitors_never_read_each_other_s_agenda(self, match, other_match, favorite_team, server_side_cache):
        one, two = Client(), Client()
        star(one, "team", match.local)
        star(two, "team", other_match.local)

        first = listed_teams(one.get(reverse("favorites")).content.decode())
        second = listed_teams(two.get(reverse("favorites")).content.decode())

        assert first == {match.local.name, match.visitor.name}
        assert second == {other_match.local.name, other_match.visitor.name}


class TestWhatOneVisitorMayKeep:
    """No database and no browser: the rule itself, so a failure names the rule."""

    def test_the_cap_holds(self):
        """It bounds the cookie against the browser's 4 KB ceiling, the `IN` clause the
        listing becomes, and the length of a page whose whole point is being short."""
        selection = Selection()

        for entity_id in range(1, MAX_PER_KIND + 11):
            selection = selection.toggled("competition", entity_id)

        assert len(selection.competitions) == MAX_PER_KIND

    def test_reaching_it_drops_the_oldest_rather_than_refusing(self):
        """Somebody who has fifty and stars a fifty-first meant to star it. An error page
        about a limit they were never told about is a worse answer than making room."""
        selection = Selection()

        for entity_id in range(1, MAX_PER_KIND + 2):
            selection = selection.toggled("competition", entity_id)

        assert 1 not in selection.competitions
        assert MAX_PER_KIND + 1 in selection.competitions

    def test_the_two_kinds_are_counted_apart(self):
        selection = Selection(teams=tuple(range(1, MAX_PER_KIND + 1)))

        selection = selection.toggled("competition", 1)

        assert selection.competitions == (1,)
        assert len(selection.teams) == MAX_PER_KIND


@pytest.mark.django_db
class TestTheStarIsTheOnlyWriteThisSiteAccepts:
    def test_it_refuses_a_get(self, client, team_home):
        """A star that worked over GET would be pressed by every crawler walking the site."""
        response = client.get(reverse("toggle-favorite-team", args=[team_home.pk]))

        assert response.status_code == 405

    def test_it_refuses_an_id_that_names_nothing(self, client):
        """Checked before anything is written, so no invented number reaches the cookie."""
        assert client.post(reverse("toggle-favorite-team", args=[999])).status_code == 404

    def test_it_sends_the_visitor_back_to_the_page_they_pressed_it_on(self, client, team_home):
        response = star(client, "team", team_home)

        assert response.status_code == 302
        assert response["Location"] == reverse("team-events", args=[team_home.pk])

    def test_it_is_protected_against_another_site_posting_it(self, team_home):
        strict = Client(enforce_csrf_checks=True)

        assert strict.post(reverse("toggle-favorite-team", args=[team_home.pk])).status_code == 403

    def test_the_cookie_cannot_be_read_by_a_script_or_sent_across_sites(self, client, team_home):
        star(client, "team", team_home)

        cookie = client.cookies[COOKIE_NAME]
        assert cookie["httponly"]
        assert cookie["samesite"] == "Lax"

    def test_the_cookie_is_marked_secure_where_the_site_is(self, client, team_home, settings):
        settings.SESSION_COOKIE_SECURE = True

        star(client, "team", team_home)

        assert client.cookies[COOKIE_NAME]["secure"]

    def test_the_cookie_stays_inside_what_a_browser_will_keep(self, visitor, sport):
        """Browsers drop a cookie over 4 KB, and dropping this one loses the selection."""
        for index in range(MAX_PER_KIND + 10):
            star(visitor, "competition", Competition.objects.create(name=f"Comp {index}", sport=sport))

        assert len(visitor.cookies[COOKIE_NAME].value) < 4096


@pytest.mark.django_db
class TestTheStarSurvivesTheProxy:
    """The one path local development cannot exercise by accident, and the site's first write.

    Development is plain HTTP, where Django skips the origin check on a POST entirely.
    Production terminates TLS at Traefik and forwards the scheme in a header, and there
    Django compares the browser's `Origin` against the site's own — so a missing
    `CSRF_TRUSTED_ORIGINS`, or `SECURE_PROXY_SSL_HEADER` left unset, turns every star press
    into a 403 that nothing here would have shown. Two outages in this project came from
    exactly this shape: something the proxy adds, or does not, that local never sees.

    The settings below are what `.env.production` carries. That file is unversioned, so this
    is a copy rather than the source; what the tests state is what the deployment must satisfy.
    """

    @pytest.fixture(autouse=True)
    def behind_the_proxy(self, settings):
        settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
        settings.CSRF_TRUSTED_ORIGINS = ["https://www.mojon.es"]
        # `testserver` is the test client's own default host, kept so a case in this class
        # can use the plain helper; the cases about the proxy name the real host themselves.
        settings.ALLOWED_HOSTS = ["www.mojon.es", "localhost", "testserver"]
        settings.USE_X_FORWARDED_HOST = True

    @staticmethod
    def as_the_proxy_sends_it(extra=None):
        return {"host": "www.mojon.es", "x-forwarded-proto": "https", **(extra or {})}

    def test_a_star_pressed_over_https_is_accepted(self, match, team_home):
        browser = Client(enforce_csrf_checks=True)
        page = browser.get(reverse("team-events", args=[team_home.pk]), headers=self.as_the_proxy_sends_it())
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()).group(1)

        response = browser.post(
            reverse("toggle-favorite-team", args=[team_home.pk]),
            {"csrfmiddlewaretoken": token},
            headers=self.as_the_proxy_sends_it({"origin": "https://www.mojon.es"}),
        )

        assert response.status_code == 302

    def test_and_one_pressed_from_another_site_is_not(self, match, team_home):
        """The half the origin check exists for."""
        browser = Client(enforce_csrf_checks=True)
        page = browser.get(reverse("team-events", args=[team_home.pk]), headers=self.as_the_proxy_sends_it())
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()).group(1)

        response = browser.post(
            reverse("toggle-favorite-team", args=[team_home.pk]),
            {"csrfmiddlewaretoken": token},
            headers=self.as_the_proxy_sends_it({"origin": "https://evil.example"}),
        )

        assert response.status_code == 403

    def test_the_cookie_it_sets_is_scoped_to_this_application(self, match, team_home, settings):
        """`.env.production` puts the site under `/soccertime`, and the cookie has to follow
        it: at `/` it would be sent to every sibling application on the same host."""
        settings.SESSION_COOKIE_PATH = "/soccertime/"
        browser = Client()

        star(browser, "team", team_home)

        assert browser.cookies[COOKIE_NAME]["path"] == "/soccertime/"


@pytest.mark.django_db
class TestACookieNobodyCanForge:
    def test_a_tampered_cookie_is_ignored(self, visitor, match, other_match, favorite_team):
        """It is signed with the site's secret, so an edited one reads as no selection at all
        and the visitor gets the curated page rather than one of their choosing."""
        star(visitor, "team", other_match.local)
        visitor.cookies[COOKIE_NAME] = visitor.cookies[COOKIE_NAME].value[:-4] + "beef"

        html = visitor.get(reverse("favorites")).content.decode()

        assert listed_teams(html) == {match.local.name, match.visitor.name}

    def test_a_cookie_that_is_not_ours_at_all_is_ignored(self, visitor, match, favorite_team):
        visitor.cookies[COOKIE_NAME] = "not-even-signed"

        html = visitor.get(reverse("favorites")).content.decode()

        assert listed_teams(html) == {match.local.name, match.visitor.name}


@pytest.mark.django_db
class TestNoTokenEndsUpInASharedCache:
    """The trap that decided where the star could live.

    Rendering `{% csrf_token %}` makes Django set `Set-Cookie: csrftoken` on that response.
    Stored in a cache shared by everybody, that response hands the same token and the same
    cookie to every other visitor, which undoes exactly what the token is for. So the rule is
    that a page with a form is never in the shared cache, and these keep it.
    """

    @pytest.mark.parametrize("page", CACHED_PAGES)
    def test_no_cached_page_renders_one(self, client, page, all_events, favorites):
        html = client.get(reverse(page)).content.decode()

        assert "csrfmiddlewaretoken" not in html

    @pytest.mark.parametrize("page", CACHED_PAGES)
    def test_no_cached_page_sets_a_cookie(self, client, page, all_events, favorites):
        assert "Set-Cookie" not in client.get(reverse(page)).headers

    @pytest.mark.parametrize("page", ["team-events", "competition-events"])
    def test_the_pages_that_do_carry_a_form_are_kept_private(self, client, page, match, team_home, competition):
        entity = team_home if page == "team-events" else competition

        response = client.get(reverse(page, args=[entity.pk]))

        assert "private" in response.headers["Cache-Control"]

    def test_a_personalised_listing_is_kept_private_too(self, visitor, match, team_home):
        """The listings say it as loudly as the pages carrying a form do.

        Without any `Cache-Control` a proxy in between is free to store what it likes and
        hand it on, and only `Vary: Cookie` would be standing between one visitor's agenda
        and the next one's.
        """
        star(visitor, "team", team_home)

        response = visitor.get(reverse("favorites"))

        assert "private" in response.headers["Cache-Control"]

    def test_and_the_shared_one_is_not(self, client, match, favorite_team):
        """`private` on the shared copy would stop proxies caching what they should."""
        assert "private" not in client.get(reverse("favorites")).headers["Cache-Control"]

    @pytest.mark.parametrize("page", ["favorites", "team-events"])
    def test_a_page_that_reads_the_cookie_says_so(self, client, page, match, team_home):
        """Without this a proxy in between could reuse one visitor's page for another."""
        args = [team_home.pk] if page == "team-events" else []

        response = client.get(reverse(page, args=args))

        assert "Cookie" in response.headers.get("Vary", "")


@pytest.mark.django_db
class TestTheStarShowsWhatItKnows:
    def test_it_is_unpressed_before_anything_is_chosen(self, client, match, team_home):
        html = client.get(reverse("team-events", args=[team_home.pk])).content.decode()

        assert 'aria-pressed="false"' in html

    def test_it_is_pressed_afterwards(self, visitor, match, team_home):
        star(visitor, "team", team_home)

        html = visitor.get(reverse("team-events", args=[team_home.pk])).content.decode()

        assert 'aria-pressed="true"' in html

    def test_a_sport_page_offers_nothing_to_star(self, client, match, sport):
        """Sports are not favouritable; a star there would store an id nothing filters on."""
        html = client.get(reverse("sport-events", args=[sport.pk])).content.decode()

        assert "favorite-star" not in html

    def test_the_competition_listing_keeps_its_cache_and_its_stars_off(self, client, match, competition):
        """It is the heaviest page on the site, so it stays shared; a competition is starred
        from its own page instead."""
        html = client.get(reverse("competitions")).content.decode()

        assert "favorite-star" not in html


@pytest.mark.django_db
class TestTheCuratedRuleIsUntouched:
    def test_a_match_in_a_favourite_competition_is_still_not_curated(
        self, client, match_in_progress, favorite_competition
    ):
        """The default page is exactly what it was; only a visitor's own selection reads a
        competition as covering its matches."""
        html = client.get(reverse("favorites")).content.decode()

        assert event_rows(html) == []

    def test_a_race_in_a_favourite_competition_still_is(self, client, race, competition_tour):
        Favorite.objects.create(competition=competition_tour, order=9)

        html = client.get(reverse("favorites")).content.decode()

        assert len(event_rows(html)) == 1


@pytest.mark.django_db
class TestThePagesThatLeftTheCachePayTheirOwnWay:
    """Carrying a form costs these pages the shared cache, so what they render is now
    rendered on every visit rather than once an hour. A busy competition took 1.6s whole,
    measured against production data — unbounded listings are affordable when they are
    computed hourly and not when they are computed per request."""

    @pytest.mark.parametrize("page", ["team-events", "competition-events"])
    def test_they_paginate(self, client, page, competition, team_home):
        for index in range(30):
            Match.objects.create(
                competition=competition,
                local=team_home,
                visitor=Team.objects.create(name=f"Rival {index}"),
                date=timezone.now() + datetime.timedelta(hours=2, minutes=index),
            )
        entity = team_home if page == "team-events" else competition

        html = client.get(reverse(page, args=[entity.pk])).content.decode()

        assert len(event_rows(html)) == 25

    def test_the_crest_strip_lists_everyone_who_plays_in_the_competition(
        self, client, competition, team_home, team_away, team_third, crested_team
    ):
        """Rewritten as two plain lookups after the page left the cache: the `OR` across home
        and away matches made SQLite join the event table twice and sort it distinct, which
        measured **1,608 ms against 19 ms** on the NBA's production data. This pins the answer
        so the faster shape cannot quietly return a different one."""
        Match.objects.create(
            competition=competition,
            local=crested_team,
            visitor=team_home,
            date=timezone.now() + datetime.timedelta(hours=1),
        )

        html = client.get(reverse("competition-events", args=[competition.pk])).content.decode()

        assert strip_team_ids(html) == {crested_team.pk}

    def test_and_the_rest_of_the_listing_is_still_reachable(self, client, competition, team_home):
        for index in range(30):
            Match.objects.create(
                competition=competition,
                local=team_home,
                visitor=Team.objects.create(name=f"Rival {index}"),
                date=timezone.now() + datetime.timedelta(hours=2, minutes=index),
            )

        html = client.get(reverse("competition-events", args=[competition.pk]), {"page": 2}).content.decode()

        assert len(event_rows(html)) == 5


@pytest.mark.django_db
class TestTodayBeginsWhereTheSiteIsRead:
    """`start_of_today()` replaced `date__date__gte=localdate()` in the three places that ask
    which competitions and sports have something upcoming. Same rows, and an index can be used
    on them — 585 ms against 8 ms and 696 ms against 84 ms on production data.

    What these pin is the boundary, because the fast form is the one that can get it wrong:
    built from `now()` instead of `localtime()` it would place midnight two hours late in
    Madrid, and for those two hours an event at 00:30 would fall out of a listing that claims
    to start at the beginning of today. The project has been bitten by exactly this before.
    """

    def test_an_event_just_after_local_midnight_counts_as_today(self, client, competition, team_home, team_away):
        just_after_midnight = timezone.localtime().replace(hour=0, minute=30, second=0, microsecond=0)
        Match.objects.create(competition=competition, local=team_home, visitor=team_away, date=just_after_midnight)

        html = client.get(reverse("competitions")).content.decode()

        assert competition.name in html

    def test_an_event_just_before_it_does_not(self, client, competition, team_home, team_away):
        just_before_midnight = timezone.localtime().replace(
            hour=23, minute=30, second=0, microsecond=0
        ) - datetime.timedelta(days=1)
        Match.objects.create(competition=competition, local=team_home, visitor=team_away, date=just_before_midnight)

        html = client.get(reverse("competitions")).content.decode()

        assert competition.name not in html

    def test_the_flag_strip_uses_the_same_boundary(
        self, client, competition, team_home, team_away, favorite_competition
    ):
        just_after_midnight = timezone.localtime().replace(hour=0, minute=30, second=0, microsecond=0)
        Match.objects.create(competition=competition, local=team_home, visitor=team_away, date=just_after_midnight)

        html = client.get(reverse("agenda")).content.decode()

        assert strip_competition_ids(html) == {competition.pk}


@pytest.mark.django_db
class TestTheStripsAndTheBorderFollowTheVisitorToo:
    """The shortcuts at the top of every page, and the gold border in the listings.

    Leaving them curated would have meant a site that contradicts itself: your agenda
    filtered to my teams, above a strip of yours, beside rows bordered as yours. They read
    the same selection now, on the same terms as the landing page — the listings stay in the
    shared cache for everybody who has chosen nothing, and are rendered fresh for whoever has.
    """

    def test_the_flag_strip_shows_the_visitor_s_competitions(
        self, visitor, match, favorite_team, competition_tour, race
    ):
        star(visitor, "competition", competition_tour)

        html = visitor.get(reverse("agenda")).content.decode()

        assert strip_competition_ids(html) == {competition_tour.pk}

    def test_and_the_owner_s_to_everybody_else(self, client, match, favorite_competition, competition):
        html = client.get(reverse("agenda")).content.decode()

        assert strip_competition_ids(html) == {competition.pk}

    def test_the_crest_strip_shows_the_visitor_s_teams(self, visitor, match, favorite_team, crested_team):
        star(visitor, "team", crested_team)

        html = visitor.get(reverse("agenda")).content.decode()

        assert strip_team_ids(html) == {crested_team.pk}

    def test_the_border_marks_the_visitor_s_events(self, visitor, match, other_match, favorite_team):
        star(visitor, "team", other_match.local)

        html = visitor.get(reverse("agenda")).content.decode()

        assert len(bordered_rows(html)) == 1
        assert f"/team/{other_match.local_id}/" in str(bordered_rows(html)[0])

    def test_and_the_owner_s_for_everybody_else(self, client, match, other_match, favorite_team):
        html = client.get(reverse("agenda")).content.decode()

        assert f"/team/{match.local_id}/" in str(bordered_rows(html)[0])

    def test_the_competition_listing_highlights_the_visitor_s(
        self, visitor, match, favorite_competition, competition_champions, match_future
    ):
        star(visitor, "competition", competition_champions)

        html = visitor.get(reverse("competitions")).content.decode()

        assert highlighted_competition_ids(html) == {competition_champions.pk}

    def test_a_listing_is_still_shared_by_everybody_who_chose_nothing(
        self, client, match, favorite_team, server_side_cache, django_assert_num_queries
    ):
        """The half that keeps the site fast: every crawler and every first visit is here."""
        client.get(reverse("agenda"))

        with django_assert_num_queries(0):
            client.get(reverse("agenda"))

    def test_and_a_personalised_one_never_reaches_the_next_visitor(
        self, match, other_match, favorite_team, server_side_cache, competition_tour
    ):
        chooser = Client()
        star(chooser, "competition", competition_tour)
        chooser.get(reverse("agenda"))

        html = Client().get(reverse("agenda")).content.decode()

        assert competition_tour.pk not in strip_competition_ids(html)


@pytest.mark.django_db
class TestTheOwnerSeesTheirOwnEditsAtOnce:
    """Nothing invalidated the page cache when a `Favorite` changed, so a strip edited in the
    admin went on showing the old one until the next hourly scrape happened to clear it."""

    def test_adding_one_clears_the_page_cache(self, client, match, competition, server_side_cache):
        client.get(reverse("agenda"))

        Favorite.objects.create(competition=competition, order=1)

        assert strip_competition_ids(client.get(reverse("agenda")).content.decode()) == {competition.pk}

    def test_removing_one_does_too(self, client, match, favorite_competition, competition, server_side_cache):
        client.get(reverse("agenda"))

        favorite_competition.delete()

        assert strip_competition_ids(client.get(reverse("agenda")).content.decode()) == set()


@pytest.mark.django_db
def test_the_selection_survives_a_visit_to_another_page(visitor, match, team_home):
    """The cookie is the only copy there is, so anything that dropped it would lose it."""
    star(visitor, "team", team_home)
    visitor.get(reverse("agenda"))

    html = visitor.get(reverse("team-events", args=[team_home.pk])).content.decode()

    assert 'aria-pressed="true"' in html


@pytest.mark.django_db
def test_an_event_is_never_listed_twice(visitor, match, favorite_team):
    """A match whose competition and both teams are all starred matches three ways."""
    star(visitor, "team", match.local)
    star(visitor, "team", match.visitor)
    star(visitor, "competition", match.competition)

    html = visitor.get(reverse("favorites")).content.decode()

    assert len(event_rows(html)) == 1
