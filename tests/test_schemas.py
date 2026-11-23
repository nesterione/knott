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
    ReferenceShape,
    ScalarType,
    iter_references,
    notation,
    shape_kind,
)

from .conftest import fixture_path, triples, validate_fixture


def _concept(root: Path, rel: str, text: str) -> None:
    path = root / ".knott/concepts" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_concepts_are_discovered_recursively_and_identified_by_name() -> None:
    vault = Knott.open(fixture_path("valid-vault"))
    assert vault.types() == ["feedback", "script", "transcript"]
    paths = {info.type: info.path for info in vault.schemas()}
    assert paths["transcript"] == ".knott/concepts/podcast/transcript.md"
    descriptions = {info.type: info.description for info in vault.schemas()}
    assert descriptions["script"] == "A script for a recorded episode."


def test_only_md_files_are_concepts(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    _concept(tmp_path, "ignored.yaml", "name: ignored\n")
    _concept(tmp_path, "ignored.markdown", "---\nname: ignored\n---\n")
    assert Knott.open(tmp_path).types() == []


def test_duplicate_name_names_both_files() -> None:
    result = validate_fixture("duplicate-schema-type")
    assert triples(result) == [(".knott/concepts/script.md", 2, "schema-duplicate-type")]
    assert result.issues[0].field == "name"
    message = result.issues[0].message
    assert ".knott/concepts/legacy/script.md" in message
    assert ".knott/concepts/script.md" in message
    # The first definition (by sorted path) stays loaded; the type is listed once.
    assert Knott.open(fixture_path("duplicate-schema-type")).types() == ["script", "transcript"]


def test_unknown_target_type() -> None:
    result = validate_fixture("unknown-relation-target-type")
    assert triples(result) == [(".knott/concepts/review.md", 6, "schema-unknown-target")]
    assert result.issues[0].field == "properties.about.target"
    assert "`episode`" in result.issues[0].message


def test_unknown_target_is_kept_aside() -> None:
    registry, issues = load_schemas(fixture_path("unknown-relation-target-type"))
    assert registry["review"].properties["about"].shape == ReferenceShape((), ("episode",))
    assert [i.code for i in issues] == ["schema-unknown-target"]
    # References with known targets keep them.
    derived = registry["transcript"].properties["derived_from"].shape
    assert derived == ReferenceShape(("script",))


def test_reference_with_only_unknown_targets_still_resolves_paths(
    copy_fixture: Callable[[str], Path],
) -> None:
    vault = copy_fixture("unknown-relation-target-type")
    (vault / "reviews").mkdir()
    (vault / "reviews" / "r1.md").write_text(
        '---\ntype: review\nabout: "[Episode](../scripts/episode-42.md)"\n---\n', encoding="utf-8"
    )
    result = Knott.open(vault).validate()
    # The path resolves; the target-type check is skipped.
    assert triples(result) == [(".knott/concepts/review.md", 6, "schema-unknown-target")]
    assert result.stats.entities == 2


def test_unknown_targets_in_union_items_and_object_fields(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    _concept(tmp_path, "person.md", "---\nname: person\n---\n")
    _concept(
        tmp_path,
        "talk.md",
        "---\n"  # 1
        "name: talk\n"  # 2
        "properties:\n"  # 3
        "  sources:\n"  # 4
        "    type: list\n"  # 5
        "    items:\n"  # 6
        "      type: reference\n"  # 7
        "      target: [person, episode, meeting]\n"  # 8
        "  speakers:\n"  # 9
        "    type: list\n"  # 10
        "    items:\n"  # 11
        "      type: object\n"  # 12
        "      fields:\n"  # 13
        "        who:\n"  # 14
        "          type: reference\n"  # 15
        "          target:\n"  # 16
        "            - person\n"  # 17
        "            - robot\n"  # 18
        "---\n",
    )
    registry, issues = load_schemas(tmp_path)
    assert [(i.field, i.line, i.code) for i in issues] == [
        ("properties.sources.items.target", 8, "schema-unknown-target"),
        ("properties.sources.items.target", 8, "schema-unknown-target"),
        ("properties.speakers.items.fields.who.target", 18, "schema-unknown-target"),
    ]
    assert "`episode`" in issues[0].message and "`meeting`" in issues[1].message
    references = list(iter_references(registry["talk"]))
    assert references == [
        (("sources", "items"), ReferenceShape(("person",), ("episode", "meeting"))),
        (("speakers", "items", "fields", "who"), ReferenceShape(("person",), ("robot",))),
    ]


def test_reference_shapes_at_any_depth(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    _concept(
        tmp_path,
        "t.md",
        "---\nname: t\nproperties:\n"
        "  one: {type: reference, target: t, required: true, description: The one.}\n"
        "  many:\n    type: list\n    items: {type: reference, target: [t, u]}\n"
        "  by_key:\n    type: map\n    values: {type: reference, target: u}\n"
        "---\n",
    )
    _concept(tmp_path, "u.md", "---\nname: u\n---\n")
    registry, issues = load_schemas(tmp_path)
    assert issues == []
    props = registry["t"].properties
    assert props["one"] == AttributeDef(
        "one", ReferenceShape(("t",)), required=True, description="The one."
    )
    assert props["many"].shape == ListShape(AttributeDef(None, ReferenceShape(("t", "u"))))
    assert props["by_key"].shape == MapShape(AttributeDef(None, ReferenceShape(("u",))))
    assert shape_kind(props["one"].shape) == "reference"
    assert notation(props["one"].shape) == "reference → t"
    assert notation(props["many"].shape) == "list of reference → t | u"
    assert notation(ReferenceShape((), ("x",))) == "reference"
    assert [path for path, _ in iter_references(registry["t"])] == [
        ("one",),
        ("many", "items"),
        ("by_key", "values"),
    ]


def test_schema_unknown_keys_and_invalid_fields() -> None:
    result = validate_fixture("schema-unknown-key")
    assert [(i.path, i.line, i.field, i.code) for i in result.issues] == [
        (".knott/concepts/Bad_Name.md", 2, "name", "schema-invalid-field"),
        (".knott/concepts/bad-fields.md", 4, "properties.type", "schema-invalid-field"),
        (".knott/concepts/bad-fields.md", 7, "properties.size.type", "schema-invalid-field"),
        (".knott/concepts/bad-fields.md", 8, "properties.size.required", "schema-invalid-field"),
        (".knott/concepts/bad-fields.md", 11, "properties.extra.default", "schema-invalid-field"),
        (".knott/concepts/bad-fields.md", 15, "properties.link.relation", "relation-unknown"),
        (".knott/concepts/broken.md", 2, None, "schema-invalid-yaml"),
        (".knott/concepts/note.md", 3, "atributes", "schema-invalid-field"),
    ]
    messages = {i.field: i.message for i in result.issues}
    assert "reserved for the entity type" in messages["properties.type"]
    assert (
        "names relation `derived`, which no relation file" in messages["properties.link.relation"]
    )


def test_concept_with_field_errors_still_defines_its_type() -> None:
    vault = Knott.open(fixture_path("schema-unknown-key"))
    assert vault.types() == ["bad", "note", "script", "transcript"]


@pytest.mark.parametrize(
    ("text", "line", "field", "fragment"),
    [
        (
            "---\ntype: t\n---\n",
            2,
            "type",
            "concept files use `name:`; `type:` belongs to entities",
        ),
        (
            "---\nname: t\nattributes: {}\n---\n",
            3,
            "attributes",
            "merged into `properties` (decision 0010); run `knott migrate`",
        ),
        (
            "---\nname: t\nrelations: {}\n---\n",
            3,
            "relations",
            "merged into `properties` (decision 0010); run `knott migrate`",
        ),
        ("---\ndescription: no name\n---\n", None, "name", "missing required key `name`"),
    ],
)
def test_top_level_key_messages(
    tmp_path: Path, text: str, line: int | None, field: str, fragment: str
) -> None:
    Knott.init(tmp_path)
    _concept(tmp_path, "t.md", text)
    issues = [i for i in Knott.open(tmp_path).schema_issues() if i.field == field]
    assert [(i.line, i.code) for i in issues] == [(line, "schema-invalid-field")]
    assert fragment in issues[0].message


def test_concept_file_needs_frontmatter(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    _concept(tmp_path, "plain.md", "# Just a note\n")
    _concept(tmp_path, "list.md", "---\n- a\n- b\n---\n")
    _concept(tmp_path, "empty.md", "---\n---\n")
    _concept(tmp_path, "unclosed.md", "---\nname: x\n")
    result = Knott.open(tmp_path).validate()
    assert triples(result) == [
        (".knott/concepts/empty.md", 1, "schema-invalid-yaml"),
        (".knott/concepts/list.md", 1, "schema-invalid-yaml"),
        (".knott/concepts/plain.md", 1, "schema-invalid-yaml"),
        (".knott/concepts/unclosed.md", 1, "schema-invalid-yaml"),
    ]
    plain = next(i for i in result.issues if i.path.endswith("plain.md"))
    assert "a concept file needs YAML frontmatter" in plain.message


def test_definitions_without_type_or_target(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    _concept(
        tmp_path,
        "t.md",
        "---\nname: t\nproperties:\n  a:\n    required: true\n  r:\n    type: reference\n---\n",
    )
    issues = Knott.open(tmp_path).schema_issues()
    assert [(i.field, i.line) for i in issues] == [("properties.a", 4), ("properties.r", 6)]
    assert "has type reference but no `target`" in issues[1].message


def test_aliased_definition_keeps_strict_required(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    _concept(
        tmp_path,
        "t.md",
        "---\nname: t\nproperties:\n  a: &a {type: string, required: yes}\n  b: *a\n---\n",
    )
    result = Knott.open(tmp_path).validate()
    assert [(i.field, i.code) for i in result.issues] == [
        ("properties.a.required", "schema-invalid-field"),
        ("properties.b.required", "schema-invalid-field"),
    ]


def test_structured_attributes_load_as_a_shape_tree() -> None:
    registry, issues = load_schemas(fixture_path("structured-attributes"))
    assert issues == []
    properties = registry["lexeme"].properties
    assert properties["lemma"].shape is ScalarType.STRING
    assert properties["tags"].shape == ListShape(AttributeDef(None, ScalarType.STRING))
    senses = properties["senses"]
    assert senses.required
    assert isinstance(senses.shape, ListShape)
    item = senses.shape.items
    assert (item.name, item.required, item.description) == (None, False, "One sense per meaning.")
    assert isinstance(item.shape, ObjectShape)
    assert list(item.shape.fields) == ["id", "ru"]
    assert item.shape.fields["ru"] == AttributeDef(
        "ru", ScalarType.STRING, required=True, description="Russian gloss"
    )
    forms = properties["forms"].shape
    assert forms == MapShape(AttributeDef(None, MapShape(AttributeDef(None, ScalarType.STRING))))
    assert notation(forms) == "map of map of string"
    assert notation(senses.shape) == "list of object"
    # `type` is reserved only at the top level.
    review = properties["review"].shape
    assert isinstance(review, ObjectShape)
    assert list(review.fields) == ["type", "done"]
    assert list(iter_references(registry["lexeme"])) == []


def _schema_issues(tmp_path: Path, properties: str) -> list[tuple[str | None, int | None, str]]:
    Knott.init(tmp_path)
    _concept(tmp_path, "t.md", "---\nname: t\nproperties:\n" + properties + "---\n")
    return [(i.field, i.line, i.message) for i in Knott.open(tmp_path).schema_issues()]


@pytest.mark.parametrize(
    ("properties", "field", "line", "fragment"),
    [
        ("  a: {type: list}\n", "properties.a", 4, "has type list but no `items`"),
        ("  a: {type: map}\n", "properties.a", 4, "has type map but no `values`"),
        ("  a: {type: object}\n", "properties.a", 4, "has type object but no `fields`"),
        ("  a:\n    type: object\n    fields: {}\n", "properties.a.fields", 6, "empty mapping"),
        ("  a:\n    type: list\n    items: string\n", "properties.a.items", 6, "must be a mapping"),
        (
            "  a:\n    type: string\n    items: {type: string}\n",
            "properties.a.items",
            6,
            "only allowed when `type` is list, but `type` is string",
        ),
        (
            "  a:\n    type: list\n    fields: {x: {type: string}}\n    items: {type: string}\n",
            "properties.a.fields",
            6,
            "only allowed when `type` is object",
        ),
        (
            "  a:\n    type: string\n    target: script\n",
            "properties.a.target",
            6,
            "only allowed when `type` is reference, but `type` is string",
        ),
        (
            "  a:\n    type: list\n    items: {type: string, required: true}\n",
            "properties.a.items.required",
            6,
            "put `required` on the list itself",
        ),
        (
            "  a:\n    type: list\n    items: {type: reference, target: t, required: true}\n",
            "properties.a.items.required",
            6,
            "put `required` on the list itself",
        ),
        (
            "  a:\n    type: map\n    values:\n      type: string\n      required: true\n",
            "properties.a.values.required",
            8,
            "put `required` on the map itself",
        ),
        (
            "  a:\n    type: list\n    items:\n      type: object\n      fields:\n"
            "        x: {type: strin}\n",
            "properties.a.items.fields.x.type",
            9,
            "unknown property type `strin`; expected one of: string, integer, number, "
            "boolean, date, datetime, list, object, map, reference",
        ),
        (
            "  a:\n    type: list\n    items: {type: string, default: x}\n",
            "properties.a.items.default",
            6,
            "unknown key `default` in `properties.a.items`; allowed keys: type, description",
        ),
        (
            "  a:\n    type: map\n    values: {description: no type}\n",
            "properties.a.values",
            6,
            "`properties.a.values` is missing `type`",
        ),
        (
            "  a: {type: reference, target: t, relation: about}\n",
            "properties.a.relation",
            4,
            "names relation `about`, which no relation file in `.knott/relations/` defines",
        ),
        (
            "  a: {type: reference, target: []}\n",
            "properties.a.target",
            4,
            "non-empty list of type names, got an empty list",
        ),
        (
            "  a: {type: reference, target: 3}\n",
            "properties.a.target",
            4,
            "must be a type name or a non-empty list of type names, got integer",
        ),
        (
            "  a:\n    type: reference\n    target:\n      - t\n      - t\n",
            "properties.a.target.1",
            8,
            "`target` lists type `t` twice",
        ),
        (
            "  a:\n    type: reference\n    target: [t, null]\n",
            "properties.a.target.1",
            6,
            "`target` item 2 must be a type name",
        ),
    ],
)
def test_invalid_definitions(
    tmp_path: Path, properties: str, field: str, line: int, fragment: str
) -> None:
    issues = _schema_issues(tmp_path, properties)
    assert [(f, ln) for f, ln, _ in issues] == [(field, line)]
    assert fragment in issues[0][2]


def test_invalid_nested_definition_drops_the_whole_property(tmp_path: Path) -> None:
    _schema_issues(
        tmp_path,
        "  ok: {type: string}\n  bad:\n    type: object\n    fields:\n"
        "      x: {type: string}\n      y: {type: nope}\n"
        "  ref: {type: reference, target: [t, t]}\n",
    )
    registry, issues = load_schemas(tmp_path)
    assert list(registry["t"].properties) == ["ok"]
    assert [i.field for i in issues] == ["properties.bad.fields.y.type", "properties.ref.target.1"]


def test_description_is_allowed_on_items_and_values(tmp_path: Path) -> None:
    issues = _schema_issues(
        tmp_path,
        "  a:\n    type: list\n    items: {type: string, description: one tag}\n"
        "  b:\n    type: map\n    values: {type: integer, description: a count}\n",
    )
    assert issues == []


def test_kid_required_concept_key(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    _concept(tmp_path, "a.md", "---\nname: a\nkid: required\n---\n")
    _concept(tmp_path, "b.md", "---\nname: b\n---\n")
    _concept(tmp_path, "c.md", "---\nname: c\nkid: optional\n---\n")
    registry, issues = load_schemas(tmp_path)
    assert (registry["a"].kid_required, registry["b"].kid_required) == (True, False)
    assert not registry["c"].kid_required
    assert [(i.path, i.line, i.field) for i in issues] == [(".knott/concepts/c.md", 3, "kid")]
    assert issues[0].message == (
        "`kid` must be `required`, got `optional`; omit it to make `kid` optional"
    )


def test_kid_is_a_reserved_property_name(tmp_path: Path) -> None:
    issues = _schema_issues(
        tmp_path,
        "  kid: {type: string}\n"
        "  meta:\n    type: object\n    fields:\n      kid: {type: string}\n",
    )
    # Only the top-level property is reserved; a nested object may have a `kid` field.
    assert [(f, ln) for f, ln, _ in issues] == [("properties.kid", 4)]
    assert "reserved for the knott-managed entity identity" in issues[0][2]


def test_template_is_stored_verbatim(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    body = "# Transcript\n\n<!-- Who speaks and what it covers. -->\n"
    _concept(tmp_path, "a.md", "---\nname: a\n---\n" + body)
    _concept(tmp_path, "b.md", "---\nname: b\n---\n")
    _concept(tmp_path, "c.md", "---\nname: c\n---\n\n   \n")
    registry, issues = load_schemas(tmp_path)
    assert issues == []
    assert registry["a"].template == body
    assert registry["b"].template is None
    assert registry["c"].template is None


def test_entity_body_is_never_checked_against_the_template(tmp_path: Path) -> None:
    # Decision 0010 §3: the template is guidance only. An empty concept body,
    # even with no newline after the closing `---`, is no template.
    Knott.init(tmp_path)
    _concept(tmp_path, "a.md", "---\nname: a\n---\n# A\n\n## Summary\n<!-- Required. -->\n")
    _concept(tmp_path, "b.md", "---\nname: b\n---")
    (tmp_path / "x.md").write_text("---\ntype: a\n---\nNo headings at all.\n")
    (tmp_path / "y.md").write_text("---\ntype: b\n---\n# Anything\n")
    registry, issues = load_schemas(tmp_path)
    assert issues == []
    assert registry["b"].template is None
    result = Knott.open(tmp_path).validate()
    assert result.ok, result.issues
    assert result.stats.entities == 2


def test_legacy_layout_is_one_issue_and_no_types(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    _concept(tmp_path, "a.md", "---\nname: a\n---\n")
    (tmp_path / ".knott/schemas").mkdir()
    (tmp_path / ".knott/schemas/a.yaml").write_text("type: a\n")
    registry, issues = load_schemas(tmp_path)
    assert registry == {}
    assert [(i.path, i.line, i.field, i.code) for i in issues] == [
        (".knott/schemas", None, None, "schema-legacy-layout")
    ]
    assert "knott migrate" in issues[0].message
