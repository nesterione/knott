from __future__ import annotations

from typing import Any

import pytest

from knott.errors import KnottError, MigrateError
from knott.schema.migrate import convert_legacy, legacy_list_fields
from knott.vault.entity import parse_markdown


def frontmatter(text: str) -> dict[str, Any]:
    assert text.startswith("---\n") and text.endswith("---\n")
    parsed = parse_markdown(text, "concept.md")
    assert parsed.error is None
    assert parsed.frontmatter is not None
    return parsed.frontmatter


def test_attributes_pass_through_unchanged_and_relation_becomes_reference() -> None:
    nested = {
        "type": "list",
        "required": True,
        "items": {
            "type": "object",
            "fields": {
                "lang": {"type": "string", "required": True},
                "tags": {"type": "map", "values": {"type": "integer"}},
            },
        },
    }
    data = {
        "type": "transcript",
        "attributes": {
            "title": {"type": "string", "required": True},
            "senses": nested,
        },
        "relations": {
            "derived_from": {"target": "script", "required": True, "description": "Source."},
        },
    }
    assert frontmatter(convert_legacy(data, set())) == {
        "name": "transcript",
        "properties": {
            "title": {"type": "string", "required": True},
            "senses": nested,
            "derived_from": {
                "type": "reference",
                "target": "script",
                "required": True,
                "description": "Source.",
            },
        },
    }


def test_list_used_relation_becomes_list_of_reference_with_required_on_list() -> None:
    data = {
        "type": "decision",
        "relations": {
            "affects": {"target": "concept", "required": True, "description": "Concepts."},
            "supersedes": {"target": "decision"},
        },
    }
    result = frontmatter(convert_legacy(data, {"affects"}))
    assert result["properties"] == {
        "affects": {
            "type": "list",
            "required": True,
            "description": "Concepts.",
            "items": {"type": "reference", "target": "concept"},
        },
        "supersedes": {"type": "reference", "target": "decision"},
    }


def test_key_order_is_name_description_kid_then_attributes_then_relations() -> None:
    data = {
        "relations": {"z_rel": {"target": "a"}, "a_rel": {"target": "a"}},
        "kid": "required",
        "attributes": {"zeta": {"type": "string"}, "alpha": {"type": "date"}},
        "description": "A thing.",
        "type": "a",
    }
    result = frontmatter(convert_legacy(data, set()))
    assert list(result) == ["name", "description", "kid", "properties"]
    assert list(result["properties"]) == ["zeta", "alpha", "z_rel", "a_rel"]
    assert result["kid"] == "required"


def test_descriptions_survive_including_multi_line() -> None:
    folded = "An architecture decision record: a choice made where the spec was silent.\n"
    multi = "First line.\nSecond line.\n\nNew paragraph.\n"
    long_line = "word " * 60
    data = {
        "type": "decision",
        "description": folded,
        "attributes": {
            "status": {"type": "string", "description": multi},
            "note": {"type": "string", "description": long_line.strip()},
        },
        "relations": {"affects": {"target": "concept", "description": multi}},
    }
    text = convert_legacy(data, {"affects"})
    assert "description: >\n" in text
    # Wide output: a long single-line description is never wrapped.
    assert f"description: {long_line.strip()}\n" in text
    result = frontmatter(text)
    assert result["description"] == folded
    assert result["properties"]["status"]["description"] == multi
    assert result["properties"]["note"]["description"] == long_line.strip()
    assert result["properties"]["affects"]["description"] == multi


def test_schema_without_fields_has_no_properties_key() -> None:
    assert frontmatter(convert_legacy({"type": "empty"}, set())) == {"name": "empty"}


def test_output_is_block_style() -> None:
    data = {"type": "a", "relations": {"r": {"target": "a"}}}
    assert convert_legacy(data, set()) == (
        "---\nname: a\nproperties:\n  r:\n    type: reference\n    target: a\n---\n"
    )


@pytest.mark.parametrize("data", [None, [], "type: a", 3])
def test_non_mapping_input_raises(data: Any) -> None:
    with pytest.raises(MigrateError, match="must be a YAML mapping"):
        convert_legacy(data, set())


def test_missing_type_raises() -> None:
    with pytest.raises(MigrateError, match="missing required key `type`"):
        convert_legacy({"description": "x"}, set())


def test_unknown_top_level_key_names_it() -> None:
    with pytest.raises(MigrateError, match="unknown key `fields`"):
        convert_legacy({"type": "a", "fields": {}}, set())


def test_unknown_relation_key_names_it() -> None:
    data = {"type": "a", "relations": {"r": {"target": "a", "inverse": "b"}}}
    with pytest.raises(MigrateError, match=r"unknown key `inverse` in `relations\.r`"):
        convert_legacy(data, set())


def test_relation_without_target_raises() -> None:
    with pytest.raises(MigrateError, match="relation `r` is missing `target`"):
        convert_legacy({"type": "a", "relations": {"r": {"required": True}}}, set())


def test_name_declared_as_attribute_and_relation_raises() -> None:
    data = {
        "type": "a",
        "attributes": {"x": {"type": "string"}},
        "relations": {"x": {"target": "a"}},
    }
    with pytest.raises(MigrateError, match="field `x` is declared both"):
        convert_legacy(data, set())


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"type": 3}, "`type` must be a string"),
        ({"type": "a", "attributes": ["x"]}, "`attributes` must be a mapping"),
        ({"type": "a", "relations": {"r": "script"}}, r"`relations\.r` must be a mapping"),
    ],
)
def test_malformed_sections_raise(data: dict[str, Any], message: str) -> None:
    with pytest.raises(MigrateError, match=message):
        convert_legacy(data, set())


def test_migrate_error_is_a_knott_error() -> None:
    assert issubclass(MigrateError, KnottError)


def test_legacy_list_fields_only_counts_lists_on_entities_of_that_type() -> None:
    entities: list[dict[str, Any]] = [
        {"type": "decision", "affects": ["[a](a.md)"], "supersedes": "[b](b.md)"},
        {"type": "decision", "affects": "[c](c.md)"},
        {"type": "concept", "supersedes": ["[d](d.md)"]},
        {"type": "decision", "related": ["[e](e.md)"]},
        {"title": "no type", "supersedes": ["[f](f.md)"]},
    ]
    found = legacy_list_fields("decision", ["affects", "supersedes"], entities)
    assert found == {"affects"}


def test_legacy_list_fields_empty_when_no_entities() -> None:
    assert legacy_list_fields("decision", ["affects"], []) == set()
