from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from knott import Knott
from knott.schema.models import ScalarType
from knott.schema.validator import format_field_path, type_mismatch

from .conftest import fixture_path, triples, validate_fixture


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


# --- structured attributes ---------------------------------------------------


def _validate_lexeme(tmp_path: Path, frontmatter: str) -> list[tuple[str | None, int | None, str]]:
    """Validate one entity against the structured-attributes fixture's `lexeme` schema."""
    Knott.init(tmp_path)
    schema = fixture_path("structured-attributes") / ".knott/schemas/lexeme.yaml"
    (tmp_path / ".knott/schemas/lexeme.yaml").write_bytes(schema.read_bytes())
    senses = "" if "senses:" in frontmatter else "senses: [{id: a, ru: b}]\n"
    text = "---\ntype: lexeme\nlemma: x\n" + senses + frontmatter + "---\n"
    (tmp_path / "a.md").write_text(text, encoding="utf-8")
    return [(i.field, i.line, i.code) for i in Knott.open(tmp_path).validate().issues]


def _messages(tmp_path: Path) -> list[str]:
    return [i.message for i in Knott.open(tmp_path).validate().issues]


def test_structured_attributes_fixture() -> None:
    result = validate_fixture("structured-attributes")
    assert [(i.path, i.line, i.field, i.code) for i in result.issues] == [
        ("lexemes/broken.md", 4, "tags[1]", "attribute-type-mismatch"),
        ("lexemes/broken.md", 7, "senses[0].ru", "attribute-type-mismatch"),
        ("lexemes/broken.md", 8, "senses[1].ru", "attribute-missing"),
        ("lexemes/broken.md", 9, "senses[1].rus", "attribute-unknown-field"),
        ("lexemes/broken.md", 11, "forms.sg.gen", "attribute-type-mismatch"),
        ("lexemes/broken.md", 13, "review.done", "attribute-type-mismatch"),
    ]
    messages = {i.field: i.message for i in result.issues}
    assert messages["senses[1].rus"] == (
        "unknown field `rus` in attribute `senses[1]`; allowed fields: id, ru; did you mean `ru`?"
    )
    assert "quote the value" in messages["senses[0].ru"]
    assert "write true or false" in messages["review.done"]
    assert "empty list item" in messages["tags[1]"]
    assert "empty map value" in messages["forms.sg.gen"]


def test_required_list_needs_an_item(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/t.yaml").write_text(
        "type: t\nattributes:\n  tags:\n    type: list\n    required: true\n"
        "    items: {type: string}\n"
    )
    (tmp_path / "a.md").write_text("---\ntype: t\ntags: []\n---\n")
    (tmp_path / "b.md").write_text("---\ntype: t\n---\n")
    result = Knott.open(tmp_path).validate()
    assert triples(result) == [
        ("a.md", 3, "attribute-missing"),
        ("b.md", None, "attribute-missing"),
    ]
    assert result.issues[0].message == (
        "required attribute `tags` (list of string) is missing or empty; add at least one item"
    )


@pytest.mark.parametrize(
    ("frontmatter", "expected"),
    [
        # An empty container of the declared kind is absent; optional, so fine.
        ("tags: []\nforms: {}\nreview: {}\n", []),
        ("tags:\nforms: ''\n", []),
        # An empty container of another kind is a mismatch.
        ("tags: {}\n", [("tags", 5, "attribute-type-mismatch")]),
        ("review: []\n", [("review", 5, "attribute-type-mismatch")]),
        # A value of the wrong kind is reported once, without descending.
        ("senses: friend\n", [("senses", 4, "attribute-type-mismatch")]),
        ("forms: {sg: [nom]}\n", [("forms.sg", 5, "attribute-type-mismatch")]),
        # Missing required nested fields; the line falls back to the item.
        ("senses:\n  - {ru: b}\n", [("senses[0].id", 5, "attribute-missing")]),
        # Non-string map key.
        ("forms:\n  sg: {1: x}\n", [("forms.sg", 6, "attribute-type-mismatch")]),
        # Nested strict typing (0004).
        ("review: {type: 3}\n", [("review.type", 5, "attribute-type-mismatch")]),
        ("review: {done: 'true'}\n", [("review.done", 5, "attribute-type-mismatch")]),
        ("review: {done: true}\n", []),
    ],
)
def test_structured_values(
    tmp_path: Path, frontmatter: str, expected: list[tuple[str, int, str]]
) -> None:
    assert _validate_lexeme(tmp_path, frontmatter) == expected


def test_every_nested_problem_is_reported(tmp_path: Path) -> None:
    issues = _validate_lexeme(
        tmp_path, "tags: [1, 2, ok]\nforms:\n  sg: {nom: 1}\n  pl: {nom: 2}\n"
    )
    assert [field for field, _, _ in issues] == [
        "tags[0]",
        "tags[1]",
        "forms.sg.nom",
        "forms.pl.nom",
    ]


def test_map_key_messages(tmp_path: Path) -> None:
    _validate_lexeme(tmp_path, "forms:\n  sg: {1: x}\n  pl: {yes: y}\n")
    assert _messages(tmp_path) == [
        "attribute `forms.sg` has map key `1`, which YAML reads as integer; "
        "map keys must be strings; "
        'quote the key, e.g. "1"',
        "attribute `forms.pl` has map key `true`, which YAML reads as boolean; "
        "map keys must be strings; "
        "quote the key (YAML reads unquoted yes/no/on/off as booleans)",
    ]


def test_unknown_field_without_a_close_match(tmp_path: Path) -> None:
    _validate_lexeme(tmp_path, "review: {zzz: 1}\n")
    assert _messages(tmp_path) == [
        "unknown field `zzz` in attribute `review`; allowed fields: type, done"
    ]


def test_scalar_attribute_still_rejects_empty_list(tmp_path: Path) -> None:
    assert _validate_lexeme(tmp_path, "lemma: []\n") == [("lemma", 5, "attribute-type-mismatch")]


@pytest.mark.parametrize(
    ("path", "text"),
    [
        (("title",), "title"),
        (("senses", 1, "ru"), "senses[1].ru"),
        (("forms", "sg", "acc"), "forms.sg.acc"),
        (("grid", 0, 2), "grid[0][2]"),
    ],
)
def test_format_field_path(path: tuple[str | int, ...], text: str) -> None:
    assert format_field_path(path) == text
