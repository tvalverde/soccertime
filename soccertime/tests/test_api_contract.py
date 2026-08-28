"""What every endpoint promises, whatever resource it serves.

The API only reads. The site's single write is the favourites cookie, which belongs to a
browser rather than to a caller carrying no session, so every route here answers 405 to
anything that is not a GET. That is asserted per resource rather than inferred from the
base class: a viewset swapped for a writable one would silently change what an
unauthenticated caller may do, and nothing else in the suite would notice.

The rest of this file pins the shape a client can build against — the pagination envelope,
the refusal of a malformed parameter, and the throttle — because those are the parts a
consumer writes code against and cannot see change.
"""

import pytest
from django.core.cache import caches
from django.urls import reverse

LIST_ROUTES = [
    "sport-list",
    "competition-list",
    "team-list",
    "flag-list",
    "channel-list",
    "channel-link-list",
    "channel-link-source-list",
    "event-list",
    "favorite-list",
]

WRITE_METHODS = ["post", "put", "patch", "delete"]


@pytest.mark.django_db
class TestTheApiOnlyReads:
    @pytest.mark.parametrize("route", LIST_ROUTES)
    @pytest.mark.parametrize("method", WRITE_METHODS)
    def test_no_collection_accepts_a_write(self, client, route, method):
        response = getattr(client, method)(reverse(route), data="{}", content_type="application/json")

        assert response.status_code == 405

    @pytest.mark.parametrize("method", WRITE_METHODS)
    def test_no_event_accepts_a_write(self, client, match, method):
        response = getattr(client, method)(
            reverse("event-detail", args=[match.pk]), data="{}", content_type="application/json"
        )

        assert response.status_code == 405


@pytest.mark.django_db
class TestTheEntryPoint:
    def test_the_root_names_every_collection(self, client):
        payload = client.get(reverse("api-root")).json()

        assert {"sports", "competitions", "teams", "flags", "channels", "events", "favorites"} <= set(payload)

    def test_the_root_points_at_the_documentation_and_the_schema(self, client):
        """A caller who found `/api/v1/` must be able to reach the description of it."""
        payload = client.get(reverse("api-root")).json()

        assert payload["schema"].endswith(reverse("api-schema"))
        assert payload["docs"].endswith(reverse("api-docs"))


@pytest.mark.django_db
class TestTheRepresentationIsJson:
    def test_a_listing_answers_json(self, client):
        response = client.get(reverse("event-list"))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

    def test_a_browser_asking_for_html_still_gets_json(self, client):
        """The browsable API is off, so a page of forms cannot leak into a GET.

        Browsers send `*/*` at the end of their Accept header, so this is what one visiting
        the endpoint by hand receives.
        """
        response = client.get(reverse("event-list"), headers={"accept": "text/html,application/xhtml+xml,*/*;q=0.8"})

        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

    def test_a_missing_record_is_reported_as_json(self, client):
        response = client.get(reverse("event-detail", args=[999999]))

        assert response.status_code == 404
        assert "detail" in response.json()


@pytest.mark.django_db
class TestPagination:
    def test_a_listing_travels_in_an_envelope(self, client, all_events):
        payload = client.get(reverse("event-list")).json()

        assert set(payload) == {"count", "next", "previous", "results"}
        assert payload["count"] == len(all_events)

    def test_the_page_size_can_be_chosen(self, client, all_events):
        payload = client.get(reverse("event-list"), {"page_size": 2}).json()

        assert len(payload["results"]) == 2
        assert payload["next"] is not None

    def test_the_page_size_is_bounded(self, client, all_events):
        """An unbounded page would let one request render the whole table."""
        payload = client.get(reverse("event-list"), {"page_size": 10000}).json()

        assert payload["count"] == len(all_events)
        assert len(payload["results"]) <= 100

    def test_a_page_beyond_the_end_is_a_404(self, client, match):
        response = client.get(reverse("event-list"), {"page": 999})

        assert response.status_code == 404


@pytest.mark.django_db
class TestMalformedParametersAreRefused:
    """Silently ignoring one answers a different question than the one asked."""

    def test_a_boolean_that_is_neither(self, client):
        response = client.get(reverse("event-list"), {"watchable": "maybe"})

        assert response.status_code == 400

    def test_a_date_that_is_not_one(self, client):
        response = client.get(reverse("event-list"), {"date": "yesterday"})

        assert response.status_code == 400

    def test_an_identifier_that_is_not_a_number(self, client):
        response = client.get(reverse("event-list"), {"competition": "la-liga"})

        assert response.status_code == 400

    def test_a_choice_outside_the_list(self, client):
        response = client.get(reverse("event-list"), {"event_type": "regatta"})

        assert response.status_code == 400

    def test_the_message_names_the_parameter(self, client):
        """A 400 that does not say which parameter is wrong costs a support round trip."""
        payload = client.get(reverse("event-list"), {"date": "yesterday"}).json()

        assert "date" in str(payload)

    def test_an_unknown_parameter_is_ignored(self, client, match):
        """Refusing these would break every client the day a parameter is added."""
        response = client.get(reverse("event-list"), {"utm_source": "newsletter"})

        assert response.status_code == 200


@pytest.mark.django_db
class TestSearchIsBounded:
    """`icontains` over a pattern the caller chose the size of is cheap to abuse.

    `EventQuerySet.search` has capped this since before the API existed; the catalogue
    listings reach the database through `filtering.free_text`, which had not.
    """

    @pytest.mark.parametrize(
        "route", ["event-list", "team-list", "competition-list", "sport-list", "flag-list", "channel-list"]
    )
    def test_a_query_longer_than_the_fields_is_answered_without_a_like(self, client, route):
        """It cannot be inside a value no field can hold, so nothing is the exact answer."""
        response = client.get(reverse(route), {"search": "x" * 5000})

        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_a_query_of_a_workable_length_still_searches(self, client, team_home):
        """Guards the guard: a cap that swallowed every search would pass the test above."""
        response = client.get(reverse("team-list"), {"search": "real"})

        assert response.json()["count"] == 1


@pytest.mark.django_db
class TestTheThrottle:
    """A listing joins six tables, so an unbounded caller is cheap to abuse.

    The counters are kept in a cache of their own in production, and the throttle falls
    back to the default one when there is none — which is what this exercises, since the
    suite runs with a single cache configured.
    """

    @pytest.fixture
    def counting_cache(self, settings):
        """A store the throttle can count in, empty at the start of this test.

        `LocMemCache` keeps its contents in a dictionary global to the process, keyed by
        `LOCATION` — so building a new instance is not the same as having a new store, and
        without this one test's counters are the next one's starting point. That is not a
        detail of the test: it is why the production alias sets a `LOCATION` of its own.
        """
        settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        caches["default"].clear()
        return caches["default"]

    def test_a_caller_over_the_limit_is_refused(self, client, settings, counting_cache):
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"api": "2/min"}}

        first = client.get(reverse("sport-list"))
        second = client.get(reverse("sport-list"))
        third = client.get(reverse("sport-list"))

        assert [first.status_code, second.status_code] == [200, 200]
        assert third.status_code == 429

    def test_a_forged_forwarded_header_does_not_buy_a_fresh_allowance(self, client, settings, counting_cache):
        """The limit is worth nothing if the caller chooses which bucket they are counted in.

        DRF reads the identity from `X-Forwarded-For` when there is one, and without
        `NUM_PROXIES` it uses the **whole** header — so a different value per request is a
        different bucket per request. One proxy stands in front and appends the peer's
        address to whatever arrived, so what is sent here is what Traefik would pass on: a
        forged prefix, then the real client. Only the last entry may decide the bucket.
        """
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"api": "2/min"}}

        statuses = [
            client.get(
                reverse("sport-list"), headers={"x-forwarded-for": f"203.0.113.{index}, 198.51.100.7"}
            ).status_code
            for index in range(3)
        ]

        assert statuses == [200, 200, 429]

    def test_two_real_callers_are_counted_apart(self, client, settings, counting_cache):
        """The other half: the limit must not be shared, or one caller exhausts everybody's."""
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"api": "1/min"}}

        first = [client.get(reverse("sport-list"), headers={"x-forwarded-for": "198.51.100.7"}).status_code]
        first.append(client.get(reverse("sport-list"), headers={"x-forwarded-for": "198.51.100.7"}).status_code)
        other = client.get(reverse("sport-list"), headers={"x-forwarded-for": "198.51.100.9"}).status_code

        assert first == [200, 429]
        assert other == 200

    def test_nothing_is_throttled_while_no_cache_records_it(self, client, settings):
        """Development and the test suite run on a dummy cache, and must stay usable."""
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"api": "1/min"}}

        statuses = [client.get(reverse("sport-list")).status_code for _ in range(3)]

        assert statuses == [200, 200, 200]
