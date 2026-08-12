"""The favourites a visitor picked for themselves, carried in a cookie they hold.

Every public page is cached for an hour and served to everybody, so whatever tells one
visitor apart from another has to travel in the request or the page of one ends up served
to the other. That leaves two carriers, the URL or a cookie, and this is the cookie.

It is signed with the site's secret and holds the ids themselves, so there is no row to
create: a stranger posting a thousand times leaves nothing behind but their own cookie,
where a session table would have grown a thousand rows. The price is that rotating
`DJANGO_SECRET_KEY` forgets everybody's selection, which is a fair trade for a list of
favourites and would not be for anything that mattered.

Django's own session framework is deliberately not used. Switching `SESSION_ENGINE` to
signed cookies would move the admin login there too, and an auth session that cannot be
revoked server-side is a worse thing to have than a list of teams.

Nothing here raises. A cookie that is missing, expired, tampered with, or written by an
older version of this code reads as "no selection", and the visitor sees the owner's
curated favourites — the same page anybody arriving for the first time gets.
"""

import json
from dataclasses import dataclass
from typing import Literal

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired
from django.http import HttpRequest, HttpResponse

COOKIE_NAME = "favorites"

# A year, renewed on every change. Long enough that a selection survives a season, and the
# cookie is the only copy there is.
COOKIE_MAX_AGE = 60 * 60 * 24 * 365

# What one visitor may keep, per kind. Not a policy about how many teams anybody could
# reasonably follow: it bounds the cookie against the browser's 4 KB ceiling, the `IN`
# clause the listing turns into, and the size of a page that exists to be short.
MAX_PER_KIND = 50

EntityKind = Literal["team", "competition"]


@dataclass(frozen=True)
class Selection:
    """The teams and competitions one visitor chose. Empty is a choice; absent is not."""

    teams: tuple[int, ...] = ()
    competitions: tuple[int, ...] = ()

    def ids_for(self, kind: EntityKind) -> tuple[int, ...]:
        return self.teams if kind == "team" else self.competitions

    def holds(self, kind: EntityKind, entity_id: int) -> bool:
        return entity_id in self.ids_for(kind)

    def toggled(self, kind: EntityKind, entity_id: int) -> "Selection":
        """The same selection with one entity added or removed.

        Adding past the cap drops the oldest, rather than refusing: a visitor who has
        reached fifty and stars a fifty-first meant to star it, and an error page about a
        limit they never knew about would be a worse answer than quietly making room.
        """
        current = self.ids_for(kind)
        if entity_id in current:
            updated = tuple(held for held in current if held != entity_id)
        else:
            updated = (*current, entity_id)[-MAX_PER_KIND:]
        if kind == "team":
            return Selection(teams=updated, competitions=self.competitions)
        return Selection(teams=self.teams, competitions=updated)


def _clean_ids(values: object) -> tuple[int, ...]:
    """Whatever came out of the cookie, as at most `MAX_PER_KIND` distinct positive ids."""
    if not isinstance(values, list):
        return ()
    cleaned: list[int] = []
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0 and value not in cleaned:
            cleaned.append(value)
    return tuple(cleaned[:MAX_PER_KIND])


def read_selection(request: HttpRequest) -> Selection | None:
    """What this visitor chose, or None if they have chosen nothing.

    The distinction matters: None falls back to the owner's curated favourites, while an
    empty `Selection` is somebody who removed the last one and should be told their agenda
    is empty rather than handed somebody else's.
    """
    try:
        raw = request.get_signed_cookie(COOKIE_NAME, default=None, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    return Selection(teams=_clean_ids(payload.get("teams")), competitions=_clean_ids(payload.get("competitions")))


def write_selection(response: HttpResponse, selection: Selection) -> HttpResponse:
    """Store the selection on the visitor's browser.

    `httponly` because no script of ours reads it — the filtering happens on the server —
    and `samesite="Lax"` so another site cannot make somebody's browser change it.
    """
    response.set_signed_cookie(
        COOKIE_NAME,
        json.dumps({"teams": list(selection.teams), "competitions": list(selection.competitions)}),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return response
