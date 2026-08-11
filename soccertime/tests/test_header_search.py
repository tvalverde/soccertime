"""The header search, which has to fit three different amounts of room.

The `.container` inside the header is 720px from 768px up, 960px from 992 and 1140px from
1200, while the logo takes about 170px and the menu 435px. The search box is 410px wide, so
it only ever fitted beside them at 1200 — and since it was shown from 992 with
`d-none d-lg-flex`, it spent the whole 992-1199 range wrapping onto a second line, left
aligned under the logo.

Below 992 it now hides behind a magnifier that reveals it, and from 992 it is inline and
narrowed. Bootstrap's own collapse does the revealing through `data-bs-toggle`, a data
attribute its script reads rather than an inline handler, so nothing here needs a script of
ours or an exception in the Content-Security-Policy.

What these tests protect is the wiring: the button points at the form by id, and the form
keeps the two classes that make it collapsed below lg and always open above it. Break
either and the magnifier silently stops working, with nothing failing anywhere else.
"""

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse


@pytest.fixture
def header(client, db):
    soup = BeautifulSoup(client.get(reverse("favorites")).content, "html.parser")
    return soup.select_one("header")


@pytest.mark.django_db
class TestTheMagnifierIsWiredToTheSearch:
    def test_the_button_targets_the_form(self, header):
        button = header.select_one('[data-bs-toggle="collapse"]')
        form = header.select_one('form[role="search"]')

        assert button["data-bs-target"] == f"#{form['id']}"

    def test_the_button_only_exists_below_the_breakpoint_that_shows_the_form(self, header):
        """`d-lg-none` on one and `d-lg-flex` on the other: never both, never neither."""
        button = header.select_one('[data-bs-toggle="collapse"]')
        form = header.select_one('form[role="search"]')

        assert "d-lg-none" in button["class"]
        assert "d-lg-flex" in form["class"]

    def test_the_form_is_collapsed_by_default(self, header):
        """Without `collapse` the box would simply always be there, wrapping as before."""
        form = header.select_one('form[role="search"]')

        assert "collapse" in form["class"]
        assert "show" not in form["class"]

    def test_the_button_says_what_it_does(self, header):
        button = header.select_one('[data-bs-toggle="collapse"]')

        assert button.get("aria-label")
        assert button["aria-expanded"] == "false"
        assert button["aria-controls"] == button["data-bs-target"].lstrip("#")

    def test_no_inline_handler_is_used(self, header):
        """The collapse is driven by data attributes, which is what keeps the CSP strict."""
        button = header.select_one('[data-bs-toggle="collapse"]')

        assert not any(name.startswith("on") for name in button.attrs)
