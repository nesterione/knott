from __future__ import annotations

from pathlib import Path

from knott import Knott

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
