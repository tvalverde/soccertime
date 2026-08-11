"""`ALLOWED_HOSTS` is what stops the site trusting a hostname the client chose.

Production ran with `*`, which disables the check entirely, while `USE_X_FORWARDED_HOST`
tells Django to read the host out of a header. Traefik only routes the two real
hostnames, so this was defence in depth rather than an open door — but it is the layer
that catches the day the proxy rule is loosened or something reaches the container
directly, and responses are cached for an hour, which is what turns one poisoned absolute
URL into everyone's problem.

The list is easy to tighten and easy to tighten wrongly. The container's health check does
not go through the proxy: it asks `http://localhost:8000/healthz/` directly, so dropping
`localhost` makes Django answer it 400, the container is marked unhealthy and the proxy
withdraws the route — the site goes down while the application is working perfectly. That
has happened here before, from `SECURE_SSL_REDIRECT`, and the test below is here so it
cannot happen again from this direction.
"""

import pytest

# What `.env.production` carries. That file is deliberately unversioned, so this is a
# copy rather than the source; the tests state what the list has to satisfy.
PRODUCTION_HOSTS = ["www.mojon.es", "mojon.es", "localhost", "127.0.0.1"]


class TestTheProductionHostList:
    @pytest.fixture(autouse=True)
    def production_settings(self, settings):
        settings.ALLOWED_HOSTS = PRODUCTION_HOSTS
        settings.USE_X_FORWARDED_HOST = True

    def test_the_container_health_check_is_allowed(self, client):
        """It bypasses the proxy, so it arrives with the host it dialled."""
        response = client.get("/healthz/", headers={"host": "localhost:8000"})

        assert response.status_code == 200

    @pytest.mark.parametrize("host", ["www.mojon.es", "mojon.es"])
    def test_both_public_hostnames_are_allowed(self, client, host):
        """Traefik routes the bare domain as well as the www one, and neither redirects."""
        response = client.get("/healthz/", headers={"host": host})

        assert response.status_code == 200

    def test_an_unknown_host_is_rejected(self, client):
        response = client.get("/healthz/", headers={"host": "evil.example"})

        assert response.status_code == 400

    def test_a_forwarded_host_is_validated_too(self, client):
        """The point of the change: `USE_X_FORWARDED_HOST` reads a header the client sets.

        With `ALLOWED_HOSTS` at `*` this answered 200 and Django would then build absolute
        URLs — cached for an hour, and served to everyone — from a hostname an attacker
        chose.
        """
        response = client.get(
            "/healthz/",
            headers={"host": "localhost:8000", "x-forwarded-host": "evil.example"},
        )

        assert response.status_code == 400


def test_dropping_localhost_takes_the_site_down(client, settings):
    """Why `localhost` is in the list, recorded as an executable fact rather than a comment.

    A list of just the public hostnames looks tighter and is the obvious thing to write.
    It also makes the health check fail, which is how the proxy learns to stop routing to
    a container that is answering every real request correctly.
    """
    settings.ALLOWED_HOSTS = ["www.mojon.es", "mojon.es"]
    settings.USE_X_FORWARDED_HOST = True

    response = client.get("/healthz/", headers={"host": "localhost:8000"})

    assert response.status_code == 400
