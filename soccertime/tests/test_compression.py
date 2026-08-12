"""Whether the pages are compressed on the way out, and what that does to revalidation.

Nothing compressed anything: not Django, not nginx, not Traefik. So `/competitions/` really
did send its 331 KB and `/channels/` its 181 KB, and the favourites page grew twelve-fold the
moment it started carrying the whole window for the browser to filter — 36.6 KB to 437.1 KB,
measured against a copy of the production database.

Compressed, that same page is 38.1 KB: the same bytes today's uncompressed one costs. The
markup is repetitive enough that gzip returns better than eleven to one on it.

The half worth testing is not the compression, which is a middleware doing its documented
job. It is the interaction with `cached_page`: that design leans on a cheap revalidation,
where `ConditionalGetMiddleware` answers with a 304 and no body. `GZipMiddleware` rewrites
the ETag it sets, appending `;gzip`, so the validator a browser stores is not the one the
next response computes. If that broke the 304, every revalidation would re-send the whole
page and the compression would have bought nothing — so a browser that asks for gzip, which
is every browser, is what these tests use.
"""

import gzip

import pytest
from django.urls import reverse

PUBLIC_PAGES = ["favorites", "agenda", "competitions", "channels"]

BROWSER = {"accept-encoding": "gzip, deflate, br"}


@pytest.mark.django_db
class TestThePagesAreCompressed:
    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_a_browser_that_asks_for_gzip_gets_it(self, client, page, all_events):
        response = client.get(reverse(page), headers=BROWSER)

        assert response.headers.get("Content-Encoding") == "gzip"

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_a_client_that_does_not_ask_gets_the_page_as_it_was(self, client, page, all_events):
        """Anything reading the site with curl or a script keeps working unchanged."""
        response = client.get(reverse(page))

        assert "Content-Encoding" not in response.headers

    def test_the_body_is_the_page(self, client, all_events):
        """Compressed, not mangled: what comes back has to decompress to the same markup."""
        compressed = client.get(reverse("agenda"), headers=BROWSER)
        plain = client.get(reverse("agenda"))

        assert gzip.decompress(compressed.content) == plain.content

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_a_cache_is_told_the_encoding_matters(self, client, page, all_events):
        """Without this a proxy could hand a gzipped body to a client that cannot read it."""
        response = client.get(reverse(page), headers=BROWSER)

        assert "Accept-Encoding" in response.headers.get("Vary", "")

    def test_it_is_worth_doing(self, client, all_events):
        """The agenda's markup is repetitive; the measured return on the real page is 11.5:1."""
        compressed = client.get(reverse("agenda"), headers=BROWSER)

        assert len(gzip.decompress(compressed.content)) > 4 * len(compressed.content)


@pytest.mark.django_db
class TestRevalidationStillCostsNothing:
    """The reason `cached_page` gives browsers `max-age=0, must-revalidate` at all."""

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_an_unchanged_page_answers_304_to_a_real_browser(self, client, page, all_events):
        first = client.get(reverse(page), headers=BROWSER)

        second = client.get(reverse(page), headers={**BROWSER, "if-none-match": first.headers["ETag"]})

        assert second.status_code == 304
        assert not second.content

    def test_the_validator_says_which_body_it_stands_for(self, client, all_events):
        """A compressed body and a plain one are different bytes, so they cannot share an ETag:
        a proxy holding one would otherwise answer the other's revalidation with a 304."""
        compressed = client.get(reverse("agenda"), headers=BROWSER)
        plain = client.get(reverse("agenda"))

        assert compressed.headers["ETag"] != plain.headers["ETag"]

    def test_a_stale_validator_still_gets_the_page(self, client, all_events):
        response = client.get(reverse("agenda"), headers={**BROWSER, "if-none-match": '"not-the-current-one"'})

        assert response.status_code == 200
        assert response.content
