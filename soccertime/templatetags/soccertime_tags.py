from typing import Any

from django.core.paginator import Paginator
from django.template.defaulttags import register
from django.utils.safestring import SafeString

from soccertime.rendering import image_markup


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


@register.filter
def elided_pages(page: Any) -> list[Any]:
    """The page numbers to offer, with `Paginator.ELLIPSIS` standing in for the gaps.

    Django works this out already, so the template only has to render it: two pages either
    side of the current one and the first and last always present, which for page 10 of 20
    gives `[1, '...', 8, 9, 10, 11, 12, '...', 20]` and for three pages gives no gap at all.
    """
    return list(page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1))


@register.filter
def is_ellipsis(value: Any) -> bool:
    """Whether an entry from `elided_pages` is a gap rather than a page number.

    Comparing against `Paginator.ELLIPSIS` rather than the literal `'...'`, so a Django
    release that changes the marker does not silently turn every gap into a page link.
    """
    return value == Paginator.ELLIPSIS
