"""The OpenAPI description and the page that renders it.

The schema is generated from the code on request, so it cannot drift from the API — but
it can quietly stop describing it, which is what `--fail-on-warn` is for: an endpoint
drf-spectacular cannot resolve is documented as an untyped blob and nobody notices until
a client is written against it.

The documentation page has to obey the same Content-Security-Policy as every other page
here, which rules out the stock template: it loads Swagger UI from a CDN and initialises
it from an inline script, and both are refused by a policy that allows `self` and nothing
else. The assets are served from this origin and the initialisation lives in a static
file, and the last class is what keeps it that way.
"""

import json

import pytest
import yaml
from django.core.management import call_command
from django.urls import reverse
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.settings import patched_settings

COLLECTIONS = [
    "/api/v1/sports/",
    "/api/v1/competitions/",
    "/api/v1/teams/",
    "/api/v1/flags/",
    "/api/v1/channels/",
    "/api/v1/channel-links/",
    "/api/v1/channel-link-sources/",
    "/api/v1/events/",
    "/api/v1/favorites/",
]


def schema(client):
    return client.get(reverse("api-schema"), {"format": "json"}).json()


@pytest.mark.django_db
class TestTheSchemaIsServed:
    def test_it_is_an_openapi_document(self, client):
        document = schema(client)

        assert document["openapi"].startswith("3.")
        assert document["info"]["title"] == "Soccertime API"
        assert document["info"]["version"]

    def test_the_document_is_openapi_yaml_by_default(self, client):
        """`?format=json` is the other half, and is what the documentation page asks for."""
        response = client.get(reverse("api-schema"))

        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/vnd.oai.openapi")
        assert yaml.safe_load(response.content)["info"]["title"] == "Soccertime API"

    @pytest.mark.parametrize("collection", COLLECTIONS)
    def test_every_collection_is_described(self, client, collection):
        assert collection in schema(client)["paths"]

    @pytest.mark.parametrize("collection", COLLECTIONS)
    def test_every_record_is_described(self, client, collection):
        assert f"{collection}{{id}}/" in schema(client)["paths"]

    def test_only_reading_is_described(self, client):
        """The document is a contract: describing a write nothing accepts would be a lie."""
        verbs = {"get", "post", "put", "patch", "delete"}
        methods = {method for path in schema(client)["paths"].values() for method in path if method in verbs}

        assert methods == {"get"}

    def test_the_filters_are_documented(self, client):
        """A parameter that only exists in the code cannot be used by anybody."""
        parameters = {
            parameter["name"] for parameter in schema(client)["paths"]["/api/v1/events/"]["get"]["parameters"]
        }

        assert {"search", "watchable", "favorites", "upcoming", "date", "competition", "team", "channel"} <= parameters

    def test_the_pagination_is_documented(self, client):
        parameters = {
            parameter["name"] for parameter in schema(client)["paths"]["/api/v1/events/"]["get"]["parameters"]
        }

        assert {"page", "page_size"} <= parameters


@pytest.mark.django_db
class TestTheSchemaDescribesWhatIsActuallyThere:
    def test_it_generates_without_a_warning_and_validates(self, tmp_path):
        """`--fail-on-warn` raises when an endpoint could not be resolved into types."""
        call_command("spectacular", "--fail-on-warn", "--validate", "--file", str(tmp_path / "schema.yaml"))

    def test_the_paths_carry_the_prefix_production_is_served_under(self):
        """Production runs under `/soccertime`, which no URL pattern here knows about.

        Without it the "try it out" button on the documentation page would call a path
        that does not exist there — and the mistake is invisible in development, where
        the prefix is empty.
        """
        with patched_settings({"SCHEMA_PATH_PREFIX_INSERT": "/soccertime"}):
            paths = SchemaGenerator().get_schema(request=None, public=True)["paths"]

        assert "/soccertime/api/v1/events/" in paths


@pytest.mark.django_db
class TestTheDocumentationPage:
    def test_it_renders(self, client):
        assert client.get(reverse("api-docs")).status_code == 200

    def test_it_loads_swagger_from_this_origin(self, client):
        html = client.get(reverse("api-docs")).content.decode()

        assert "drf_spectacular_sidecar/swagger-ui-dist/swagger-ui-bundle.js" in html
        assert "drf_spectacular_sidecar/swagger-ui-dist/swagger-ui.css" in html

    def test_it_loads_nothing_from_a_third_party(self, client):
        """`script-src 'self'` refuses these, so the page would render an empty box."""
        html = client.get(reverse("api-docs")).content.decode()

        assert "unpkg.com" not in html
        assert "cdn.jsdelivr.net" not in html

    def test_it_names_the_schema_without_an_inline_script(self, client):
        """The URL travels in a data attribute, which the static initialiser reads."""
        html = client.get(reverse("api-docs")).content.decode()

        assert f'data-schema-url="{reverse("api-schema")}' in html
        assert "soccertime/js/api_docs.js" in html

    def test_nothing_inline_is_rendered(self, client):
        html = client.get(reverse("api-docs")).content.decode()

        assert "<script>" not in html
        assert "<style>" not in html
        assert 'style="' not in html
        assert 'onload="' not in html

    def test_it_carries_the_policy_every_other_page_carries(self, client):
        policy = client.get(reverse("api-docs")).headers["Content-Security-Policy"]

        assert "unsafe-inline" not in policy
        assert "unsafe-eval" not in policy

    def test_the_assets_survive_the_hashing_a_deploy_applies(self, tmp_path, settings):
        """Outside development every static file is stored under a hash of its contents.

        Post-processing rewrites every reference inside a CSS or JS file and raises when
        one of them names a file that was not collected — Swagger's stylesheet and bundle
        both carry source map references. A deploy is where that would be discovered
        otherwise, and it is the failure this project has already paid for: the site
        answered 500 to every page while the health check stayed green.
        """
        settings.STATIC_ROOT = tmp_path
        settings.STORAGES = {
            **settings.STORAGES,
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
        }

        call_command("collectstatic", "--noinput", verbosity=0)

        collected = json.loads((tmp_path / "staticfiles.json").read_text())["paths"]
        assert "drf_spectacular_sidecar/swagger-ui-dist/swagger-ui-bundle.js" in collected
        assert "soccertime/js/api_docs.js" in collected

    def test_it_asks_not_to_be_indexed(self, client):
        """The whole site refuses crawlers, and a page listing every endpoint most of all."""
        html = client.get(reverse("api-docs")).content.decode()

        assert '<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">' in html


@pytest.mark.django_db
class TestTheApiIsReachable:
    def test_the_bare_prefix_leads_to_the_current_version(self, client):
        response = client.get("/api/")

        assert response.status_code in (301, 302)
        assert response["Location"].endswith(reverse("api-root"))
