"""Tests for the template filters."""

from types import SimpleNamespace

import pytest

from soccertime.templatetags.soccertime_tags import (
    normalize_subcategory,
    sort_by_list_length,
    sort_categories_by_total_links,
)


def group(name, size):
    """A regroup result: an object with a grouper and a list."""
    return SimpleNamespace(grouper=name, list=list(range(size)))


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
