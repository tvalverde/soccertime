"""The Content-Security-Policy, and the property the templates have to keep for it to work.

A CSP is the layer that contains an injection rather than preventing one: it is what would
have limited the stored XSS fixed in 0.3.2, and what limits the next hole nobody has found.
The site carried HSTS, `nosniff`, `X-Frame-Options` and a referrer policy, and no CSP.

The policy here has no `unsafe-inline` and no nonce. A nonce cannot work on this site:
every public view is cached for an hour, `cache_page` stores the response before this
middleware adds the header, and a cache hit would pair a fresh nonce in the header with a
stale one in the body — blocking every inline script for everybody but the visitor who
populated the cache. So the inline was removed instead, and the last test class is what
keeps it removed: a `style="..."` added in a hurry is silently ignored by the browser under
this policy, and the failure looks like a styling bug rather than a security one.
"""

import pytest
from django.conf import settings as django_settings
from django.urls import reverse

PUBLIC_PAGES = ["favorites", "agenda", "competitions", "channels"]


def policy(response):
    return response.headers["Content-Security-Policy"]


@pytest.mark.django_db
class TestTheHeaderIsServed:
    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_every_public_page_carries_it(self, client, page):
        response = client.get(reverse(page))

        assert "Content-Security-Policy" in response.headers

    def test_a_cached_response_carries_it_too(self, client, settings):
        """The header is added after `cache_page` has stored the body, so a hit still gets one.

        This is the same mechanism that rules a nonce out, checked from the other side.
        """
        settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        settings.CACHE_PAGE_TIMEOUT = 3600

        first = client.get(reverse("agenda"))
        second = client.get(reverse("agenda"))

        assert policy(first) == policy(second)


@pytest.mark.django_db
class TestThePolicyIsWorthHaving:
    def test_nothing_inline_is_permitted(self, client):
        """`unsafe-inline` in script-src is what turns a CSP into decoration."""
        directives = policy(client.get(reverse("agenda")))

        assert "unsafe-inline" not in directives
        assert "unsafe-eval" not in directives

    @pytest.mark.parametrize(
        ("directive", "expected"),
        [
            ("default-src", "'self'"),
            ("script-src", "'self'"),
            ("style-src", "'self'"),
            ("object-src", "'none'"),
            ("base-uri", "'none'"),
            ("frame-ancestors", "'none'"),
            ("form-action", "'self'"),
        ],
    )
    def test_each_directive_says_what_it_should(self, client, directive, expected):
        directives = dict(
            (part.split(" ", 1) + [""])[:2] for part in policy(client.get(reverse("agenda"))).split("; ")
        )

        assert directives[directive] == expected

    def test_no_third_party_host_is_allowed(self, client):
        """Bootstrap is served from this origin; the CDN it used to come from is not listed.

        Allowing `cdn.jsdelivr.net` would let a tag injected by an XSS pull any package it
        hosts. SRI protects the tags this project writes, not the ones an attacker writes.
        """
        directives = policy(client.get(reverse("agenda")))

        assert "jsdelivr" not in directives
        # `data:` for the favicon is the only source that is not this origin.
        sources = {word for word in directives.replace(";", "").split() if not word.startswith("'")}
        assert sources - set(django_settings.SECURE_CSP) == {"data:"}

    def test_the_favicon_data_uri_still_has_permission(self, client):
        """`img-src` has to allow `data:`, since the favicon is an inline SVG."""
        directives = policy(client.get(reverse("agenda")))

        assert "img-src 'self' data:" in directives


@pytest.mark.django_db
class TestThePagesHonourIt:
    """Anything inline the templates grow back is dead on arrival, so it is pinned here."""

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_no_inline_script_is_rendered(self, client, page):
        html = client.get(reverse(page)).content.decode()

        assert "<script>" not in html

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_no_inline_style_block_is_rendered(self, client, page):
        html = client.get(reverse(page)).content.decode()

        assert "<style>" not in html

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_no_style_attribute_is_rendered(self, client, page):
        """The browser ignores these under this policy, and the symptom looks cosmetic."""
        html = client.get(reverse(page)).content.decode()

        assert 'style="' not in html

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_no_inline_event_handler_is_rendered(self, client, page):
        html = client.get(reverse(page)).content.decode()

        assert 'onclick="' not in html
        assert 'onload="' not in html

    def test_the_scripts_the_pages_do_load_come_from_this_origin(self, client):
        html = client.get(reverse("agenda")).content.decode()

        assert "soccertime/vendor/bootstrap/bootstrap.bundle.min.js" in html
        assert "soccertime/js/teams_toggle.js" in html
        assert "//cdn.jsdelivr.net" not in html
