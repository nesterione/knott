from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from knott.schema.models import ScalarType
from knott.schema.validator import type_mismatch

from .conftest import triples, validate_fixture


def test_wrong_attribute_type_fixture() -> None:
    result = validate_fixture("wrong-attribute-type")
    assert triples(result) == [
        ("bool-as-int.md", 3, "attribute-type-mismatch"),
        ("datetime-as-date.md", 3, "attribute-type-mismatch"),
        ("misc.md", 3, "attribute-type-mismatch"),
        ("misc.md", 4, "attribute-type-mismatch"),
        ("misc.md", 5, "attribute-type-mismatch"),
        ("misc.md", 6, "attribute-type-mismatch"),
        ("misc.md", 7, "attribute-type-mismatch"),
        ("misc.md", 8, "attribute-type-mismatch"),
        ("unquoted-no.md", 3, "attribute-type-mismatch"),
        ("yaml11.md", 3, "attribute-type-mismatch"),  # [] is not an empty attribute
        ("yaml11.md", 4, "attribute-type-mismatch"),  # yes is not true/false
    ]


def test_yaml11_boolean_spelling_is_rejected() -> None:
    result = validate_fixture("wrong-attribute-type")
    issue = next(i for i in result.issues if i.path == "yaml11.md" and i.field == "flag")
    assert issue.message == "attribute `flag` expects boolean but got `yes`; write true or false"


def test_unquoted_no_suggests_quoting() -> None:
    result = validate_fixture("wrong-attribute-type")
    issue = next(i for i in result.issues if i.path == "unquoted-no.md")
    assert issue.field == "name"
    assert "boolean `no`" in issue.message
    assert 'quote the value (e.g. "no")' in issue.message


STR, INT, NUM, BOOL, DATE, DTIME = (
    ScalarType.STRING,
    ScalarType.INTEGER,
    ScalarType.NUMBER,
    ScalarType.BOOLEAN,
    ScalarType.DATE,
    ScalarType.DATETIME,
)
DAY = dt.date(2026, 10, 6)
MOMENT = dt.datetime(2026, 10, 6, 10, 30)


@pytest.mark.parametrize(
    ("expected", "value"),
    [
        (STR, "text"),
        (INT, 3),
        (NUM, 3),
        (NUM, 3.5),
        (BOOL, True),
        (BOOL, False),
        (DATE, DAY),
        (DATE, "2026-10-06"),
        (DTIME, MOMENT),
        (DTIME, "2026-10-06T10:30:00"),
        (DTIME, "2026-10-06T10:30:00Z"),
        (DTIME, "2026-10-06 10:30"),
    ],
)
def test_accepted_values(expected: ScalarType, value: Any) -> None:
    assert type_mismatch(expected, value) is None


@pytest.mark.parametrize(
    ("expected", "value"),
    [
        (STR, 42),
        (STR, False),
        (STR, DAY),
        (INT, True),
        (INT, 1.0),
        (INT, "1"),
        (NUM, True),
        (NUM, "1.5"),
        (BOOL, 1),
        (BOOL, "true"),
        (DATE, MOMENT),
        (DATE, "2026-10-06T10:30:00"),
        (DATE, "2026-13-45"),
        (DATE, "20261006"),
        (DTIME, DAY),
        (DTIME, "2026-10-06"),
        (DTIME, "not a time"),
        (STR, ["a"]),
    ],
)
def test_rejected_values(expected: ScalarType, value: Any) -> None:
    assert type_mismatch(expected, value) is not None
