import os
from typing import Any

from django.template.defaulttags import register
from django.utils.safestring import SafeString

from soccertime.rendering import image_markup

ENV_ALLOWLIST = frozenset({"DJANGO_DEBUG"})


@register.filter
def env(key: str, default: str = "") -> bool | str:
    """Read an allowlisted environment variable, returning the default for anything else.

    The filter is reachable from every template, so without the allowlist a single
    `{{ "DJANGO_SECRET_KEY"|env }}` would render the secret into a page.
    """
    if key not in ENV_ALLOWLIST:
        return default
    value = os.environ.get(key)
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
    return value or default


@register.filter
def sort_by_list_length(regroup_list: Any, reverse: str = "True") -> list[Any]:
    """Order regroup results by how many items each group holds, largest first.

    Usage: {% regroup items by field as grouped %}{{ grouped|sort_by_list_length }}
    """
    reverse_bool = str(reverse).lower() not in ("false", "0", "")
    items = list(regroup_list)
    return sorted(items, key=lambda x: len(x.list), reverse=reverse_bool)


@register.filter
def normalize_subcategory(value: Any) -> str:
    """Normalise a subcategory for comparisons and querystrings.

    None would render as the string "None" in a querystring, which then fails to match
    the tab it came from; both None and the empty string collapse to empty.
    """
    if value is None or value == "":
        return ""
    return str(value)


@register.filter
def sort_categories_by_total_links(regroup_list: Any, reverse: str = "True") -> list[Any]:
    """Order categories by how many links they hold in total, largest first."""
    reverse_bool = str(reverse).lower() not in ("false", "0", "")
    items = list(regroup_list)

    def count_total_links(category_group: Any) -> int:
        # The group holds one entry per link, so its length is the total
        return len(category_group.list)

    return sorted(items, key=count_total_links, reverse=reverse_bool)


@register.filter
def render_image_markup(obj: Any) -> SafeString:
    """Render an ImageMixin instance's image, or the placeholder."""
    return image_markup(obj)
