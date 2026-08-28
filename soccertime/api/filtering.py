"""Query parameters, declared once and read twice: to narrow a listing and to describe it.

A filter that exists only in `get_queryset` cannot be used by anybody, because nothing in
the schema says it is there; one declared only in the schema is a promise the code does
not keep. So each is a single `QueryFilter` carrying both halves, and the backend below
applies them and hands the same list to drf-spectacular.

A value that cannot be read is refused rather than ignored. Dropping it would answer a
different question than the one asked — `?watchable=maybe` would quietly return everything,
including what cannot be watched — and the caller would have no way to find out.
"""

import datetime
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, NoReturn

from django.db.models import Q, QuerySet
from django.utils.dateparse import parse_date
from drf_spectacular.plumbing import build_basic_type, build_parameter_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend
from rest_framework.request import Request
from rest_framework.views import APIView

from soccertime.models import MAX_SEARCHABLE_NAME_LENGTH

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})

AnyQuerySet = QuerySet[Any]
Parser = Callable[[str, str], Any]
# The queryset a narrowing receives is whatever the view built, and several of them are an
# `EventQuerySet` carrying methods a plain `QuerySet` annotation would hide — `watchable()`,
# `favorites()`, `search()`. Typing it as the base class would make every one of those a
# type error at the call site, so the shape is left to the view that supplies it.
Narrowing = Callable[[Any, Any], Any]


def refuse(name: str, raw: str, expected: str) -> NoReturn:
    """Report which parameter was wrong, not merely that one was."""
    raise ValidationError({name: f"'{raw}' is not {expected}."})


def as_boolean(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    refuse(name, raw, f"a boolean: use one of {sorted(TRUE_VALUES | FALSE_VALUES)}")


def as_integer(name: str, raw: str) -> int:
    try:
        return int(raw)
    except ValueError:
        refuse(name, raw, "a whole number")


def as_day(name: str, raw: str) -> datetime.date:
    try:
        parsed = parse_date(raw)
    except ValueError:
        parsed = None
    if parsed is None:
        refuse(name, raw, "a date in YYYY-MM-DD form")
    return parsed


def as_text(name: str, raw: str) -> str:
    return raw


def one_of(choices: Sequence[str]) -> Parser:
    def parse(name: str, raw: str) -> str:
        if raw not in choices:
            refuse(name, raw, f"one of {list(choices)}")
        return raw

    return parse


@dataclass(frozen=True)
class QueryFilter:
    """One query parameter: how to read it, what it does, and how it is documented."""

    name: str
    description: str
    narrow: Narrowing
    parse: Parser = as_text
    schema_type: Any = OpenApiTypes.STR
    choices: tuple[str, ...] | None = None

    def apply(self, queryset: AnyQuerySet, raw: str) -> AnyQuerySet:
        return self.narrow(queryset, self.parse(self.name, raw))

    def as_parameter(self) -> dict[str, Any]:
        return build_parameter_type(
            name=self.name,
            schema=build_basic_type(self.schema_type) or {},
            location=OpenApiParameter.QUERY,
            description=self.description,
            enum=list(self.choices) if self.choices else None,
        )


def switch(name: str, description: str, narrow: Callable[[Any], Any]) -> QueryFilter:
    """A flag that narrows the listing when true and leaves it untouched when false.

    Derived states get this rather than a two-way filter: the complement of "has an enabled
    link" or "is a favourite" is a second query over the same joins, and no page asks for it.
    """
    return QueryFilter(
        name=name,
        description=f"{description} Applied only when true.",
        narrow=lambda queryset, on: narrow(queryset) if on else queryset,
        parse=as_boolean,
        schema_type=OpenApiTypes.BOOL,
    )


def toggle(name: str, description: str, lookup: str) -> QueryFilter:
    """A flag over a column the database holds, which can therefore answer both ways."""
    return QueryFilter(
        name=name,
        description=description,
        narrow=lambda queryset, value: queryset.filter(**{lookup: value}),
        parse=as_boolean,
        schema_type=OpenApiTypes.BOOL,
    )


def identifier(name: str, description: str, lookup: str) -> QueryFilter:
    return QueryFilter(
        name=name,
        description=description,
        narrow=lambda queryset, value: queryset.filter(**{lookup: value}),
        parse=as_integer,
        schema_type=OpenApiTypes.INT,
    )


def exact(name: str, description: str, lookup: str, choices: tuple[str, ...] | None = None) -> QueryFilter:
    return QueryFilter(
        name=name,
        description=description,
        narrow=lambda queryset, value: queryset.filter(**{lookup: value}),
        parse=one_of(choices) if choices else as_text,
        choices=choices,
    )


def day(name: str, description: str, narrow: Callable[[Any, datetime.date], Any]) -> QueryFilter:
    return QueryFilter(
        name=name,
        description=description,
        narrow=narrow,
        parse=as_day,
        schema_type=OpenApiTypes.DATE,
    )


def free_text(description: str, *lookups: str) -> QueryFilter:
    """Case-insensitive search across the fields a caller would think to type into.

    Bounded by the length of the fields being searched, exactly as `EventQuerySet.search`
    is and for the same reason: `icontains` asks whether the query is a substring of the
    value, so one longer than the longest value a `CharField(max_length=255)` can hold
    cannot be inside any of them. Returning nothing is the exact answer, and it costs no
    `LIKE` over a pattern an anonymous caller chose the size of.
    """

    def narrow(queryset: AnyQuerySet, value: str) -> AnyQuerySet:
        if len(value) > MAX_SEARCHABLE_NAME_LENGTH:
            return queryset.none()
        matches = Q()
        for lookup in lookups:
            matches |= Q(**{f"{lookup}__icontains": value})
        return queryset.filter(matches)

    return QueryFilter(name="search", description=description, narrow=narrow)


def ordering(description: str, orderings: dict[str, Sequence[str]]) -> QueryFilter:
    """A choice between named orders, so no caller can order by an unindexed column."""
    return QueryFilter(
        name="ordering",
        description=description,
        narrow=lambda queryset, value: queryset.order_by(*orderings[value]),
        parse=one_of(tuple(orderings)),
        choices=tuple(orderings),
    )


class QueryFilterBackend(BaseFilterBackend):
    """Applies a view's `query_filters`, and tells the schema generator about them."""

    def filter_queryset(self, request: Request, queryset: AnyQuerySet, view: APIView) -> AnyQuerySet:
        for query_filter in getattr(view, "query_filters", ()):
            raw = request.query_params.get(query_filter.name)
            # An empty value is how a browser submits an untouched form field, and means
            # "no opinion" rather than "match the empty string".
            if raw is None or raw == "":
                continue
            queryset = query_filter.apply(queryset, raw)
        return queryset

    def get_schema_operation_parameters(self, view: APIView) -> list[dict[str, Any]]:
        return [query_filter.as_parameter() for query_filter in getattr(view, "query_filters", ())]
