"""How long a page may be reused, and by whom.

`cache_page` announces its own timeout to the client, so every page went out with
`Cache-Control: max-age=3600`. The server cache was the point; telling browsers the same
thing was a side effect, and a costly one: a visitor who had loaded a page went on serving
it from their own cache for the next hour without contacting the site at all. The scraper
would run, `make remote-scrape` would clear the server cache, and none of it reached anyone
who had just been there — on a listing of live events, where a channel appearing is the
whole point. A deploy took just as long to become visible.

`cached_page` keeps the server cache and drops only the browser's licence to skip the
request, with `ConditionalGetMiddleware` answering the revalidation with a 304 and no body.
The two halves are tested together here because either alone is a regression: without the
header the staleness comes back, and without the ETag every revalidation re-sends the page.
"""

import pytest
from django.urls import reverse

PUBLIC_PAGES = ["favorites", "agenda", "competitions", "channels"]


@pytest.fixture
def server_side_cache(settings):
    """The real thing rather than the dummy backend the suite runs with."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.CACHE_PAGE_TIMEOUT = 3600
    from django.core.cache import caches

    caches["default"].clear()
    return caches["default"]


@pytest.mark.django_db
class TestBrowsersHaveToAsk:
    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_no_page_may_be_reused_without_asking(self, client, page):
        response = client.get(reverse(page))

        assert response.headers["Cache-Control"] == "max-age=0, must-revalidate"

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_each_page_carries_a_validator(self, client, page):
        """Without one the revalidation would re-send the whole page every time."""
        assert client.get(reverse(page)).headers.get("ETag")

    def test_an_unchanged_page_answers_304_with_no_body(self, client):
        first = client.get(reverse("agenda"))

        second = client.get(reverse("agenda"), headers={"if-none-match": first.headers["ETag"]})

        assert second.status_code == 304
        assert not second.content

    def test_a_stale_validator_gets_the_page(self, client):
        response = client.get(reverse("agenda"), headers={"if-none-match": '"not-the-current-one"'})

        assert response.status_code == 200
        assert response.content


@pytest.mark.django_db
class TestTheServerCacheIsStillThere:
    """The expensive half. Dropping it along with the header would be the easy mistake."""

    def test_a_second_request_is_served_without_touching_the_database(
        self, client, server_side_cache, match, django_assert_num_queries
    ):
        client.get(reverse("agenda"))

        with django_assert_num_queries(0):
            client.get(reverse("agenda"))

    def test_the_cached_response_still_tells_the_browser_to_revalidate(self, client, server_side_cache, match):
        """`cache_control` is applied outside `cache_page`, so it reaches cache hits too."""
        client.get(reverse("agenda"))

        second = client.get(reverse("agenda"))

        assert second.headers["Cache-Control"] == "max-age=0, must-revalidate"

    def test_clearing_the_server_cache_reaches_the_next_visitor(self, client, server_side_cache, match):
        """What `make remote-scrape` relies on, and what the old header undid."""
        before = client.get(reverse("agenda")).headers["ETag"]
        server_side_cache.clear()
        match.delete()

        after = client.get(reverse("agenda")).headers["ETag"]

        assert before != after
