from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from knott import Knott
from knott.schema.loader import load_schemas
from knott.schema.models import (
    AttributeDef,
    ListShape,
    MapShape,
    ObjectShape,
    ScalarType,
    notation,
)

from .conftest import fixture_path, triples, validate_fixture


def test_schemas_are_discovered_recursively_and_identified_by_type() -> None:
    vault = Knott.open(fixture_path("valid-vault"))
    assert vault.types() == ["feedback", "script", "transcript"]
    paths = {info.type: info.path for info in vault.schemas()}
    assert paths["transcript"] == ".knott/schemas/podcast/transcript.yaml"
    descriptions = {info.type: info.description for info in vault.schemas()}
    assert descriptions["script"] == "A script for a recorded episode."


def test_yml_files_are_not_schemas(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/ignored.yml").write_text("type: ignored\n")
    assert Knott.open(tmp_path).types() == []


def test_duplicate_type_names_both_files() -> None:
    result = validate_fixture("duplicate-schema-type")
    assert triples(result) == [(".knott/schemas/script.yaml", 1, "schema-duplicate-type")]
    message = result.issues[0].message
    assert ".knott/schemas/legacy/script.yaml" in message
    assert ".knott/schemas/script.yaml" in message
    # The first definition (by sorted path) stays loaded; the type is listed once.
    assert Knott.open(fixture_path("duplicate-schema-type")).types() == ["script", "transcript"]


def test_unknown_relation_target_type() -> None:
    result = validate_fixture("unknown-relation-target-type")
    assert triples(result) == [(".knott/schemas/review.yaml", 4, "schema-unknown-target")]
    assert result.issues[0].field == "relations.about.target"
    assert "`episode`" in result.issues[0].message


def test_unknown_relation_target_is_kept_aside() -> None:
    registry, issues = load_schemas(fixture_path("unknown-relation-target-type"))
    review = registry["review"]
    assert review.relations == {}
    assert list(review.unknown_relations) == ["about"]
    assert review.unknown_relations["about"].target == "episode"
    assert [i.code for i in issues] == ["schema-unknown-target"]
    # Relations with known targets stay where they were.
    transcript = registry["transcript"]
    assert list(transcript.relations) == ["derived_from"]
    assert transcript.unknown_relations == {}


def test_validation_ignores_relations_to_unknown_types(
    copy_fixture: Callable[[str], Path],
) -> None:
    vault = copy_fixture("unknown-relation-target-type")
    (vault / "reviews").mkdir()
    (vault / "reviews" / "r1.md").write_text(
        '---\ntype: review\nabout: "[Missing](../nowhere.md)"\n---\n', encoding="utf-8"
    )
    result = Knott.open(vault).validate()
    assert triples(result) == [(".knott/schemas/review.yaml", 4, "schema-unknown-target")]
    assert result.stats.entities == 2


def test_schema_unknown_keys_and_invalid_fields() -> None:
    result = validate_fixture("schema-unknown-key")
    assert triples(result) == [
        (".knott/schemas/Bad_Name.yaml", 1, "schema-invalid-field"),
        (".knott/schemas/bad-fields.yaml", 3, "schema-field-conflict"),
        (".knott/schemas/bad-fields.yaml", 6, "schema-invalid-field"),
        (".knott/schemas/bad-fields.yaml", 7, "schema-invalid-field"),
        (".knott/schemas/bad-fields.yaml", 12, "schema-invalid-field"),
        (".knott/schemas/bad-fields.yaml", 14, "schema-field-conflict"),
        (".knott/schemas/broken.yaml", 2, "schema-invalid-yaml"),
        (".knott/schemas/note.yaml", 2, "schema-invalid-field"),
    ]
    by_path = {i.path: i for i in result.issues}
    assert by_path[".knott/schemas/note.yaml"].field == "atributes"


def test_schema_with_field_errors_still_defines_its_type() -> None:
    vault = Knott.open(fixture_path("schema-unknown-key"))
    assert vault.types() == ["bad", "note", "script", "transcript"]


def test_schema_must_be_a_mapping_with_type(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    schemas = tmp_path / ".knott/schemas"
    (schemas / "list.yaml").write_text("- a\n- b\n")
    (schemas / "empty.yaml").write_text("")
    (schemas / "untyped.yaml").write_text("description: no type\n")
    (schemas / "nested.yaml").write_text(
        "type: nested\nattributes:\n  a:\n    required: true\n"
        "relations:\n  r:\n    required: true\n"
    )
    result = Knott.open(tmp_path).validate()
    assert triples(result) == [
        (".knott/schemas/empty.yaml", None, "schema-invalid-yaml"),
        (".knott/schemas/list.yaml", None, "schema-invalid-yaml"),
        (".knott/schemas/nested.yaml", 3, "schema-invalid-field"),
        (".knott/schemas/nested.yaml", 6, "schema-invalid-field"),
        (".knott/schemas/untyped.yaml", None, "schema-invalid-field"),
    ]


def test_aliased_definition_keeps_strict_required(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/t.yaml").write_text(
        "type: t\nattributes:\n  a: &a {type: string, required: yes}\n  b: *a\n"
    )
    result = Knott.open(tmp_path).validate()
    assert [(i.field, i.code) for i in result.issues] == [
        ("attributes.a.required", "schema-invalid-field"),
        ("attributes.b.required", "schema-invalid-field"),
    ]


def test_structured_attributes_load_as_a_shape_tree() -> None:
    registry, issues = load_schemas(fixture_path("structured-attributes"))
    assert issues == []
    attributes = registry["lexeme"].attributes
    assert attributes["lemma"].shape is ScalarType.STRING
    assert attributes["tags"].shape == ListShape(AttributeDef(None, ScalarType.STRING))
    senses = attributes["senses"]
    assert senses.required
    assert isinstance(senses.shape, ListShape)
    item = senses.shape.items
    assert (item.name, item.required, item.description) == (None, False, "One sense per meaning.")
    assert isinstance(item.shape, ObjectShape)
    assert list(item.shape.fields) == ["id", "ru"]
    assert item.shape.fields["ru"] == AttributeDef(
        "ru", ScalarType.STRING, required=True, description="Russian gloss"
    )
    forms = attributes["forms"].shape
    assert forms == MapShape(AttributeDef(None, MapShape(AttributeDef(None, ScalarType.STRING))))
    assert notation(forms) == "map of map of string"
    assert notation(senses.shape) == "list of object"
    # `type` is reserved only at the top level.
    review = attributes["review"].shape
    assert isinstance(review, ObjectShape)
    assert list(review.fields) == ["type", "done"]


def _schema_issues(tmp_path: Path, attributes: str) -> list[tuple[str | None, int | None, str]]:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/t.yaml").write_text(
        "type: t\nattributes:\n" + attributes, encoding="utf-8"
    )
    return [(i.field, i.line, i.message) for i in Knott.open(tmp_path).schema_issues()]


@pytest.mark.parametrize(
    ("attributes", "field", "line", "fragment"),
    [
        ("  a: {type: list}\n", "attributes.a", 3, "has type list but no `items`"),
        ("  a: {type: map}\n", "attributes.a", 3, "has type map but no `values`"),
        ("  a: {type: object}\n", "attributes.a", 3, "has type object but no `fields`"),
        ("  a:\n    type: object\n    fields: {}\n", "attributes.a.fields", 5, "empty mapping"),
        ("  a:\n    type: list\n    items: string\n", "attributes.a.items", 5, "must be a mapping"),
        (
            "  a:\n    type: string\n    items: {type: string}\n",
            "attributes.a.items",
            5,
            "only allowed when `type` is list, but `type` is string",
        ),
        (
            "  a:\n    type: list\n    fields: {x: {type: string}}\n    items: {type: string}\n",
            "attributes.a.fields",
            5,
            "only allowed when `type` is object",
        ),
        (
            "  a:\n    type: list\n    items: {type: string, required: true}\n",
            "attributes.a.items.required",
            5,
            "put `required` on the list itself",
        ),
        (
            "  a:\n    type: map\n    values:\n      type: string\n      required: true\n",
            "attributes.a.values.required",
            7,
            "put `required` on the map itself",
        ),
        (
            "  a:\n    type: list\n    items:\n      type: object\n      fields:\n"
            "        x: {type: strin}\n",
            "attributes.a.items.fields.x.type",
            8,
            "unknown attribute type `strin`; expected one of: string, integer, number, "
            "boolean, date, datetime, list, object, map",
        ),
        (
            "  a:\n    type: list\n    items: {type: string, default: x}\n",
            "attributes.a.items.default",
            5,
            "unknown key `default` in `attributes.a.items`; allowed keys: type, description",
        ),
        (
            "  a:\n    type: map\n    values: {description: no type}\n",
            "attributes.a.values",
            5,
            "`attributes.a.values` is missing `type`",
        ),
    ],
)
def test_invalid_structured_definitions(
    tmp_path: Path, attributes: str, field: str, line: int, fragment: str
) -> None:
    issues = _schema_issues(tmp_path, attributes)
    assert [(f, ln) for f, ln, _ in issues] == [(field, line)]
    assert fragment in issues[0][2]


def test_invalid_nested_definition_drops_the_whole_attribute(tmp_path: Path) -> None:
    _schema_issues(
        tmp_path,
        "  ok: {type: string}\n  bad:\n    type: object\n    fields:\n"
        "      x: {type: string}\n      y: {type: nope}\n",
    )
    registry, issues = load_schemas(tmp_path)
    assert list(registry["t"].attributes) == ["ok"]
    assert [i.field for i in issues] == ["attributes.bad.fields.y.type"]


def test_description_is_allowed_on_items_and_values(tmp_path: Path) -> None:
    issues = _schema_issues(
        tmp_path,
        "  a:\n    type: list\n    items: {type: string, description: one tag}\n"
        "  b:\n    type: map\n    values: {type: integer, description: a count}\n",
    )
    assert issues == []
