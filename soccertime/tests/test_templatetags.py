"""Tests for the template filters."""

from types import SimpleNamespace

import pytest

from soccertime.templatetags.soccertime_tags import (
    env,
    normalize_subcategory,
    sort_by_list_length,
    sort_categories_by_total_links,
)


def group(name, size):
    """A regroup result: an object with a grouper and a list."""
    return SimpleNamespace(grouper=name, list=list(range(size)))


class TestEnv:
    @pytest.mark.parametrize("value,expected", [("true", True), ("True", True), ("false", False), ("FALSE", False)])
    def test_reads_an_allowlisted_variable_as_a_boolean(self, monkeypatch, value, expected):
        monkeypatch.setenv("DJANGO_DEBUG", value)
        assert env("DJANGO_DEBUG") is expected

    def test_refuses_anything_outside_the_allowlist(self, monkeypatch):
        """The filter reaches every template, so a secret must not be readable."""
        monkeypatch.setenv("DJANGO_SECRET_KEY", "super-secret")

        assert env("DJANGO_SECRET_KEY") == ""
        assert "super-secret" not in str(env("DJANGO_SECRET_KEY", "fallback"))

    def test_returns_the_default_for_a_disallowed_name(self, monkeypatch):
        monkeypatch.setenv("DJANGO_SECRET_KEY", "super-secret")
        assert env("DJANGO_SECRET_KEY", "fallback") == "fallback"

    def test_returns_the_default_when_the_variable_is_unset(self, monkeypatch):
        monkeypatch.delenv("DJANGO_DEBUG", raising=False)
        assert env("DJANGO_DEBUG", "fallback") == "fallback"

    def test_non_boolean_values_pass_through(self, monkeypatch):
        monkeypatch.setenv("DJANGO_DEBUG", "maybe")
        assert env("DJANGO_DEBUG") == "maybe"


class TestSortByListLength:
    def test_orders_from_longest_to_shortest(self):
        ordered = sort_by_list_length([group("a", 1), group("b", 3), group("c", 2)])
        assert [item.grouper for item in ordered] == ["b", "c", "a"]

    @pytest.mark.parametrize("reverse", ["False", "false", "0", ""])
    def test_can_be_reversed(self, reverse):
        ordered = sort_by_list_length([group("a", 1), group("b", 3)], reverse)
        assert [item.grouper for item in ordered] == ["a", "b"]

    def test_empty_input(self):
        assert sort_by_list_length([]) == []


class TestNormalizeSubcategory:
    @pytest.mark.parametrize("value", [None, ""])
    def test_missing_values_become_an_empty_string(self, value):
        """Templates compare this against a querystring, where None would render as "None"."""
        assert normalize_subcategory(value) == ""

    def test_keeps_a_real_value(self):
        assert normalize_subcategory("Mundial") == "Mundial"

    def test_coerces_to_string(self):
        assert normalize_subcategory(7) == "7"


class TestSortCategoriesByTotalLinks:
    def test_orders_by_number_of_links(self):
        ordered = sort_categories_by_total_links([group("few", 2), group("many", 5)])
        assert [item.grouper for item in ordered] == ["many", "few"]

    def test_can_be_reversed(self):
        ordered = sort_categories_by_total_links([group("few", 2), group("many", 5)], "false")
        assert [item.grouper for item in ordered] == ["few", "many"]
