"""Tests for the settings helpers driving deployment configuration."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from soccertime.settings import env_flag


class TestEnvFlag:
    """Transport security is switched on per environment, so parsing must be exact."""

    @pytest.mark.parametrize("value", ["true", "True", "TRUE"])
    def test_true_regardless_of_case(self, monkeypatch, value):
        monkeypatch.setenv("SOCCERTIME_TEST_FLAG", value)
        assert env_flag("SOCCERTIME_TEST_FLAG") is True

    @pytest.mark.parametrize("value", ["false", "False", "", "1", "yes", "on"])
    def test_anything_else_is_false(self, monkeypatch, value):
        """Only an explicit "true" enables a flag: a typo must never open the site up."""
        monkeypatch.setenv("SOCCERTIME_TEST_FLAG", value)
        assert env_flag("SOCCERTIME_TEST_FLAG") is False

    def test_missing_variable_is_false(self, monkeypatch):
        monkeypatch.delenv("SOCCERTIME_TEST_FLAG", raising=False)
        assert env_flag("SOCCERTIME_TEST_FLAG") is False


class TestStaticFilesAreVersioned:
    """A deploy that changes a stylesheet has to reach browsers that already hold one.

    nginx serves static files with no `Cache-Control`, only an ETag and a Last-Modified,
    so browsers cache them heuristically under a URL that never changes. The first deploy
    where that mattered was the CSP one: the styles moved out of the templates and into
    `theme.css`, pages arrived without their inline styles, browsers kept serving the
    previous `theme.css`, and the site looked broken until a forced reload.

    Reloading the settings module under a chosen environment, rather than reading
    `django.conf.settings`, which is already configured with DEBUG on for the suite.
    """

    def staticfiles_backend_with_debug(self, monkeypatch, debug):
        """Read the backend before restoring, since `reload` mutates the module in place.

        Returning the module instead would hand back a reference the restoring reload has
        already overwritten, and the assertion would silently measure the wrong run.
        """
        import importlib

        import soccertime.settings

        monkeypatch.setenv("DJANGO_DEBUG", debug)
        monkeypatch.setenv("DJANGO_SECRET_KEY", "reload-only-not-used")
        try:
            reloaded = importlib.reload(soccertime.settings)
            return reloaded.STORAGES["staticfiles"]["BACKEND"]
        finally:
            monkeypatch.undo()
            importlib.reload(soccertime.settings)

    def test_names_carry_a_content_hash_outside_development(self, monkeypatch):
        backend = self.staticfiles_backend_with_debug(monkeypatch, "false")

        assert backend == "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

    def test_development_keeps_the_plain_backend(self, monkeypatch):
        """There is no manifest before `collectstatic` has run, and reading one would fail."""
        backend = self.staticfiles_backend_with_debug(monkeypatch, "true")

        assert backend == "django.contrib.staticfiles.storage.StaticFilesStorage"


class TestTheSettingsFailClosed:
    """What happens when `.env.production` loses a line.

    That file is deliberately not in the repository, so nothing reviews it and nothing
    notices an entry going missing. The image now defaults to safe values, which means the
    interesting question is no longer "what does it fall back to" but "does it refuse".
    """

    def snapshot(self, monkeypatch, **environment):
        """Reload the settings under these variables and return the values that matter.

        A snapshot of plain values rather than the module: `importlib.reload` mutates it in
        place, so a returned reference would point at the restored version by the time the
        caller read it. Restoring in `finally` matters just as much — leaving the module
        holding a test's environment would poison every test after it.
        """
        import importlib

        import soccertime.settings

        for name, value in environment.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        try:
            reloaded = importlib.reload(soccertime.settings)
            return {"DEBUG": reloaded.DEBUG, "SECRET_KEY": reloaded.SECRET_KEY}
        finally:
            monkeypatch.undo()
            importlib.reload(soccertime.settings)

    def test_an_absent_debug_variable_leaves_debug_off(self, monkeypatch):
        """The image bakes `false`; this is the behaviour that makes that meaningful."""
        values = self.snapshot(monkeypatch, DJANGO_DEBUG=None, DJANGO_SECRET_KEY="a-key-for-the-reload")

        assert values["DEBUG"] is False

    def test_no_key_and_no_debug_refuses_to_start(self, monkeypatch):
        """The whole configuration missing must stop the container, not start it insecurely.

        It then fails its health check, the proxy withdraws the route and the site answers
        404 — which is a far better outcome than serving Django's debug page to the world.
        """
        with pytest.raises(ImproperlyConfigured):
            self.snapshot(monkeypatch, DJANGO_DEBUG=None, DJANGO_SECRET_KEY=None)

    def test_the_development_key_needs_debug_turned_on_deliberately(self, monkeypatch):
        """The hardcoded key stays reachable, but only for someone who asked for debug."""
        values = self.snapshot(monkeypatch, DJANGO_DEBUG="true", DJANGO_SECRET_KEY=None)

        assert values["SECRET_KEY"] == "dev-only-insecure-key-not-for-production"
        assert values["DEBUG"] is True
