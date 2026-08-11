"""Converting stored event times between Spanish wall clock and real UTC.

Kept out of the migration so it can be tested directly against both seasons, and so the
migration reads as the two-line call it is. There is no reason for anything else to import
this: it exists for one conversion, run once in each direction.
"""

import datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import F

MADRID = ZoneInfo("Europe/Madrid")

# SQLite's parameter limit is generous but not unlimited, and the whole point of grouping by
# offset is to avoid 52,133 individual statements.
CHUNK = 2_000


def _offset(moment: datetime.datetime, *, from_utc: bool) -> datetime.timedelta:
    """How far the stored value sits from real UTC, decided by the event's own date.

    Not a constant: Madrid is one hour ahead in winter and two in summer, and events are
    written months in advance, so the changeover falls between the scrape and the event
    routinely. Production splits 55/45 across the two.

    Going forwards the stored value *is* the Madrid wall clock, so it is read as such. Coming
    back it is real UTC, so the offset is the one in force at that instant. Either way the
    answer is the same number, which is what makes the inverse exact.
    """
    if from_utc:
        return moment.replace(tzinfo=datetime.UTC).astimezone(MADRID).utcoffset() or datetime.timedelta()
    return moment.replace(tzinfo=MADRID).utcoffset() or datetime.timedelta()


def convert_stored_dates(model: Any, *, to_utc: bool) -> int:
    """Shift every row onto the other reading of its own clock. Returns rows touched.

    Reads with `values_list` and writes with `update`, so no model instance — and no
    `post_init` handler — is ever built, per the rule this project already paid for once.
    Rows are grouped by offset, so the whole table costs one read and two updates rather than
    one statement per row.
    """
    rows = model.objects.values_list("pk", "date")
    by_offset: dict[datetime.timedelta, list[int]] = {}
    for pk, stored in rows:
        naive = stored.replace(tzinfo=None)
        by_offset.setdefault(_offset(naive, from_utc=not to_utc), []).append(pk)

    touched = 0
    for offset, pks in by_offset.items():
        shift = -offset if to_utc else offset
        for start in range(0, len(pks), CHUNK):
            batch = pks[start : start + CHUNK]
            touched += model.objects.filter(pk__in=batch).update(date=F("date") + shift)
    return touched
