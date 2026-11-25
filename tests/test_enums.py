"""Enum properties (spec 0009)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import EnumOption, Knott
from knott.cli import app
from knott.models import Issue
from knott.schema.loader import load_definitions
from knott.schema.models import EnumShape
from knott.schema.validator import closest_option
from knott.view import render_ontology

runner = CliRunner()

CONCEPT = """---
name: lexeme
properties:
  gender: { type: enum, options: [m, f] }
  level:
    type: enum
    required: true
    description: CEFR level at which the word is taught.
    options:
      A1: Understands and uses familiar everyday expressions.
      A2:   Handles simple,
        routine exchanges.
      B1:
  tags:
    type: list
    items: { type: enum, options: [colloquial, formal, archaic], description: A register. }
  answer: { type: enum, options: ["yes", "no", "1", "in review"] }
  forms:
    type: map
    values:
      type: object
      fields:
        case: { type: enum, required: true, options: [nom, gen] }
---
"""


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path, concept: str = CONCEPT) -> Path:
    Knott.init(tmp_path)
    _write(tmp_path, ".knott/concepts/lexeme.md", concept)
    return tmp_path


def _entity(root: Path, frontmatter: str) -> list[Issue]:
    _write(root, "lexemes/x.md", f"---\ntype: lexeme\n{frontmatter}---\n")
    return Knott.open(root).validate().issues


def _codes(issues: list[Issue]) -> list[tuple[str | None, int | None, str]]:
    return [(i.field, i.line, i.code) for i in issues]


# --- the shape in a concept -----------------------------------------------------


def test_options_load_in_order_with_descriptions(tmp_path: Path) -> None:
    loaded = load_definitions(_vault(tmp_path))
    assert loaded.issues == []
    props = loaded.schemas["lexeme"].properties
    assert props["gender"].shape == EnumShape((("m", None), ("f", None)))
    assert props["level"].shape == EnumShape(
        (
            ("A1", "Understands and uses familiar everyday expressions."),
            ("A2", "Handles simple, routine exchanges."),
            ("B1", None),
        )
    )


@pytest.mark.parametrize(
    ("properties", "field", "fragment"),
    [
        ("  a: { type: enum }", "properties.a", "has type enum but no `options`"),
        ("  a: { type: enum, options: [] }", "properties.a.options", "an empty list"),
        ("  a: { type: enum, options: {} }", "properties.a.options", "an empty mapping"),
        ("  a: { type: enum, options: m }", "properties.a.options", "got string `m`"),
        ("  a: { type: enum, options: [m, f, m] }", "properties.a.options.2", "twice"),
        ("  a: { type: enum, options: [m, no] }", "properties.a.options.1", 'quote it, e.g. "no"'),
        ("  a: { type: enum, options: [1] }", "properties.a.options.0", 'quote it, e.g. "1"'),
        (
            "  a: { type: enum, options: [2026-10-06] }",
            "properties.a.options.0",
            'e.g. "2026-10-06"',
        ),
        ('  a: { type: enum, options: [""] }', "properties.a.options.0", "is empty"),
        ('  a: { type: enum, options: [" m"] }', "properties.a.options.0", "whitespace"),
        ("  a: { type: enum, options: [[m]] }", "properties.a.options.0", "got list"),
        ("  a: { type: enum, options: [{m: 1}] }", "properties.a.options.0", "got mapping"),
        ("  a: { type: enum, options: [m, ~] }", "properties.a.options.1", "got null"),
        (
            "  a: { type: enum, options: { 1: x } }",
            "properties.a.options",
            "the key `1` as integer",
        ),
        ("  a: { type: enum, options: { A1: 3 } }", "properties.a.options.A1", "description"),
        ("  a: { type: string, options: [m] }", "properties.a.options", "only allowed when"),
        (
            "  a: { type: list, options: [m], items: { type: enum, options: [m] } }",
            "properties.a.options",
            "put `options:` on `items`",
        ),
        (
            "  a: { type: map, options: [m], values: { type: enum, options: [m] } }",
            "properties.a.options",
            "put `options:` on `values`",
        ),
        ("  a: { type: enum, options: [m], values: [m] }", "properties.a.values", "only allowed"),
        ("  a: { type: enum, options: [m], accept: [m] }", "properties.a.accept", "only allowed"),
    ],
)
def test_enum_definition_errors(tmp_path: Path, properties: str, field: str, fragment: str) -> None:
    root = _vault(tmp_path, f"---\nname: lexeme\nproperties:\n{properties}\n---\n")
    issues = Knott.open(root).schema_issues()
    assert [(i.field, i.code) for i in issues] == [(field, "schema-invalid-field")]
    assert fragment in issues[0].message


def test_property_with_invalid_options_is_not_loaded(tmp_path: Path) -> None:
    root = _vault(
        tmp_path, "---\nname: lexeme\nproperties:\n  a: { type: enum, options: [m, m] }\n---\n"
    )
    assert "a" not in load_definitions(root).schemas["lexeme"].properties


def test_boolean_keys_in_mapping_form_are_reported(tmp_path: Path) -> None:
    concept = (
        "---\nname: lexeme\nproperties:\n  a:\n    type: enum\n    options:\n      no: Never\n---\n"
    )
    (issue,) = Knott.open(_vault(tmp_path, concept)).schema_issues()
    assert (issue.field, issue.line, issue.code) == (
        "properties.a.options",
        6,
        "schema-invalid-field",
    )
    assert issue.message == (
        "an option must be a string, but YAML reads the key `false` as boolean; "
        "quote the key (YAML reads unquoted yes/no/on/off as booleans)"
    )


def test_unquoted_no_in_list_form_shows_the_source_spelling(tmp_path: Path) -> None:
    root = _vault(
        tmp_path, "---\nname: lexeme\nproperties:\n  a: { type: enum, options: [m, no] }\n---\n"
    )
    (issue,) = Knott.open(root).schema_issues()
    assert issue.message == (
        'an option must be a string, but YAML reads `no` as boolean; quote it, e.g. "no"'
    )


def test_single_option_enum_is_valid(tmp_path: Path) -> None:
    root = _vault(
        tmp_path, "---\nname: lexeme\nproperties:\n  a: { type: enum, options: [x] }\n---\n"
    )
    assert Knott.open(root).schema_issues() == []
    assert _entity(root, "a: x\n") == []


# --- values -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("frontmatter", "expected"),
    [
        ("level: A1\n", []),
        ('level: A1\ngender: m\ntags: [formal, archaic, formal]\nanswer: "no"\n', []),
        ('level: A1\nanswer: "in review"\n', []),
        ('level: A1\ngender: ""\ntags: []\n', []),
        ("level: A1\ngender:\n", []),
        ("", [("level", None, "attribute-missing")]),
        ("level:\n", [("level", 3, "attribute-missing")]),
        ("level: a1\n", [("level", 3, "attribute-unknown-option")]),
        ("level: A1\ngender: female\n", [("gender", 4, "attribute-unknown-option")]),
        ('level: A1\ngender: " f"\n', [("gender", 4, "attribute-unknown-option")]),
        ("level: A1\ngender: F\n", [("gender", 4, "attribute-unknown-option")]),
        ("level: A1\nanswer: no\n", [("answer", 4, "attribute-type-mismatch")]),
        ("level: A1\nanswer: 1\n", [("answer", 4, "attribute-type-mismatch")]),
        ("level: A1\ngender: [m]\n", [("gender", 4, "attribute-type-mismatch")]),
        ("level: A1\ngender: {m: 1}\n", [("gender", 4, "attribute-type-mismatch")]),
        ("level: A1\ntags: formal\n", [("tags", 4, "attribute-type-mismatch")]),
        (
            "level: A1\ntags:\n  - formal\n  - slang\n  - formal\n  - 3\n",
            [("tags[1]", 6, "attribute-unknown-option"), ("tags[3]", 8, "attribute-type-mismatch")],
        ),
        (
            "level: A1\nforms:\n  sg: { case: nom }\n  pl: { case: acc }\n  du: {}\n",
            [
                ("forms.pl.case", 6, "attribute-unknown-option"),
                ("forms.du", 7, "attribute-type-mismatch"),
            ],
        ),
    ],
)
def test_values(
    tmp_path: Path, frontmatter: str, expected: list[tuple[str, int | None, str]]
) -> None:
    assert _codes(_entity(_vault(tmp_path), frontmatter)) == expected


def test_messages(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    by_field = {
        i.field: i.message
        for i in _entity(
            root, "level: a1\ngender: female\nanswer: no\ntags: [formel]\nforms: {sg: {case: 4}}\n"
        )
    }
    assert by_field["gender"] == "attribute `gender` must be one of `m`, `f`, but got `female`"
    assert by_field["level"] == (
        "attribute `level` must be one of `A1`, `A2`, `B1`, but got `a1`; did you mean `A1`?"
    )
    assert by_field["tags[0]"].endswith("but got `formel`; did you mean `formal`?")
    assert by_field["answer"] == (
        "attribute `answer` expects enum (a string) but got boolean `no`; "
        'quote the value (e.g. "no") to make it a string'
    )
    assert by_field["forms.sg.case"].startswith(
        "attribute `forms.sg.case` expects enum (a string) but got integer `4`"
    )


@pytest.mark.parametrize(
    ("value", "options", "expected"),
    [
        ("a1", ("A1", "A2"), "A1"),
        ("femnine", ("masculine", "feminine"), "feminine"),
        ("female", ("m", "f"), None),
        ("x", ("X", "x "), "X"),
        ("ab", ("AB", "Ab"), None),
    ],
)
def test_closest_option(value: str, options: tuple[str, ...], expected: str | None) -> None:
    assert closest_option(value, options) == expected


# --- output ---------------------------------------------------------------------


def test_ontology_options(tmp_path: Path) -> None:
    (lexeme,) = Knott.open(_vault(tmp_path)).ontology().types
    by_name = {p.name: p for p in lexeme.properties}
    assert by_name["gender"].type == "enum"
    assert by_name["gender"].options == [EnumOption(value="m"), EnumOption(value="f")]
    assert by_name["level"].options[1] == EnumOption(
        value="A2", description="Handles simple, routine exchanges."
    )
    assert by_name["tags"].notation == "list of enum"
    assert by_name["tags"].options == []
    assert by_name["tags"].items is not None
    assert [o.value for o in by_name["tags"].items.options] == ["colloquial", "formal", "archaic"]
    assert lexeme.references() == []


def test_types_verbose_prints_options_under_the_property(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(_vault(tmp_path))
    result = runner.invoke(app, ["types", "--verbose"])
    assert result.exit_code == 0
    assert (
        result.stdout
        == """\
lexeme  (.knott/concepts/lexeme.md)
  template: no
  references: none
  properties:
    gender  enum
      one of: m | f
    level*  enum           CEFR level at which the word is taught.
      A1: Understands and uses familiar everyday expressions.
      A2: Handles simple, routine exchanges.
      B1
    tags    list of enum
      each item: A register.
      one of: colloquial | formal | archaic
    answer  enum
      one of: yes | no | 1 | in review
    forms   map of object
      case*  enum
        one of: nom | gen
"""
    )


def test_validate_output_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(tmp_path)
    assert _entity(root, "level: B1\n") == []
    monkeypatch.chdir(root)
    assert runner.invoke(app, ["validate"]).stdout == (
        "✓ 1 schema\n✓ 1 entity\n✓ 0 relations\n✓ vault is valid\n"
    )
    _entity(root, "level: C9\n")
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert result.stdout == (
        "✗ lexemes/x.md:3  level\n"
        "  attribute `level` must be one of `A1`, `A2`, `B1`, but got `C9`\n"
        "\n1 validation error\n"
    )


def test_view_embeds_options(tmp_path: Path) -> None:
    page = render_ontology(Knott.open(_vault(tmp_path)).ontology())
    assert (
        '"options": [{"value": "m", "description": null}, {"value": "f", "description": null}]'
        in page
    )
    assert "node.options" in page
