from typing import Any

from django.core.paginator import Paginator
from django.template.defaulttags import register
from django.utils.safestring import SafeString

from soccertime.models import Match
from soccertime.rendering import image_markup


@register.filter
def marked_favorite(parent_event: Any, selection: Any) -> bool:
    """Whether a listing row carries the gold border, for whoever is reading the page.

    Two rules, because there are two kinds of favourite. With no selection it is the owner's
    curated list, exactly as the border has always meant. With one it is the visitor's, and
    there a competition covers its matches — the same reading `for_selection()` uses, so the
    border and the landing page never disagree about what counts.

    Everything it touches is already loaded by `with_related()`, so a listing pays no query
    for it.
    """
    if selection is None:
        child = parent_event.child_event
        return bool(child and child.is_favorite_event)
    if parent_event.competition_id in selection.competitions:
        return True
    child = parent_event.child_event
    return isinstance(child, Match) and (child.local_id in selection.teams or child.visitor_id in selection.teams)


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
