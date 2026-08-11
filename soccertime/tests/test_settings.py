"""Tests for the settings helpers driving deployment configuration."""

import pytest

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
