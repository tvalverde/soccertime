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
