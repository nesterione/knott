"""Relation files and `relation:` on references (spec 0006)."""

from __future__ import annotations

from pathlib import Path

import pytest

from knott import Knott
from knott.models import Issue
from knott.schema.loader import load_ontology
from knott.schema.models import ListShape, ReferenceShape, RelationDef, iter_references
from tests.conftest import fixture_path


def _write(root: Path, rel: str, text: str) -> None:
    path = root / ".knott" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path, concepts: dict[str, str], relations: dict[str, str]) -> list[Issue]:
    Knott.init(tmp_path)
    for name, text in concepts.items():
        _write(tmp_path, f"concepts/{name}.md", text)
    for name, text in relations.items():
        _write(tmp_path, f"relations/{name}.md", text)
    return Knott.open(tmp_path).schema_issues()


def _brief(issues: list[Issue]) -> list[tuple[str, int | None, str | None, str]]:
    return [(i.path, i.line, i.field, i.code) for i in issues]


# --- the fixture vault --------------------------------------------------------


def test_fixture_vault_is_valid() -> None:
    result = Knott.open(fixture_path("relation-definitions")).validate()
    assert result.ok, result.issues


def test_relation_files_are_discovered_and_parsed() -> None:
    _, relations, issues = load_ontology(fixture_path("relation-definitions"))
    assert issues == []
    # Subfolders only organise; other file types are ignored.
    assert sorted(relations) == ["about", "covers", "related", "supersedes", "unused"]
    assert relations["supersedes"] == RelationDef(
        name="supersedes",
        description="This entity replaces the target. The target stays as history.",
        inverse="superseded_by",
        symmetric=False,
        acyclic=True,
        guidance=(
            "<!-- Use when the old entity is no longer the current answer. "
            "For a partial change, use `amends`. -->\n"
        ),
        path=".knott/relations/history/supersedes.md",
    )
    assert relations["supersedes"].lines["inverse"] == 3
    assert relations["related"].symmetric
    assert relations["related"].guidance is None
    assert relations["unused"].guidance == "\nNobody names this relation.\n"
    assert relations["unused"].inverse is None


def test_relation_is_kept_on_references_at_any_depth() -> None:
    schemas, _, _ = load_ontology(fixture_path("relation-definitions"))
    refs = {path: shape.relation for path, shape in iter_references(schemas["decision"])}
    assert refs == {
        ("supersedes",): "supersedes",
        ("affects", "items"): "about",
        ("history", "items", "fields", "replaces"): "supersedes",
    }
    guide = {path: shape.relation for path, shape in iter_references(schemas["guide"])}
    assert guide == {("main",): "covers", ("concepts", "items"): None}


def test_vault_without_relations_folder_has_no_relations(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    _write(tmp_path, "concepts/a.md", "---\nname: a\n---\n")
    schemas, relations, issues = load_ontology(tmp_path)
    assert (list(schemas), relations, issues) == (["a"], {}, [])


def test_empty_relations_folder_is_valid(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/relations").mkdir()
    assert Knott.open(tmp_path).validate().ok


# --- relation files -----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "line", "field", "code", "fragment"),
    [
        (
            "---\nname: a\ninverce: b\n---\n",
            3,
            "inverce",
            "schema-invalid-field",
            "unknown key `inverce` in relation file; allowed keys: name, description, "
            "inverse, symmetric, acyclic; did you mean `inverse`?",
        ),
        (
            "---\nname: a\ncolor: red\n---\n",
            3,
            "color",
            "schema-invalid-field",
            "unknown key `color` in relation file; allowed keys: name, description, "
            "inverse, symmetric, acyclic",
        ),
        (
            "---\nname: a\ntransitive: true\n---\n",
            3,
            "transitive",
            "schema-invalid-field",
            "`transitive` is reserved, not supported yet; remove it",
        ),
        (
            "---\nname: a\nsymmetric: yes\n---\n",
            3,
            "symmetric",
            "schema-invalid-field",
            "`symmetric` must be true or false, got boolean `yes`",
        ),
        (
            '---\nname: a\nacyclic: "true"\n---\n',
            3,
            "acyclic",
            "schema-invalid-field",
            "`acyclic` must be true or false, got string",
        ),
        (
            "---\nname: Bad\n---\n",
            2,
            "name",
            "schema-invalid-field",
            "relation name must match ^[a-z][a-z0-9_-]*$, got `Bad`",
        ),
        (
            "---\ndescription: x\n---\n",
            None,
            "name",
            "schema-invalid-field",
            "missing required key `name`",
        ),
        (
            "---\nname: a\ninverse: Has Space\n---\n",
            3,
            "inverse",
            "schema-invalid-field",
            "relation inverse must match ^[a-z][a-z0-9_-]*$",
        ),
        (
            "---\nname: a\ndescription: [x]\n---\n",
            3,
            "description",
            "schema-invalid-field",
            "expected a string, got list",
        ),
        (
            "name: a\n",
            1,
            None,
            "schema-invalid-yaml",
            "a relation file needs YAML frontmatter",
        ),
        ("---\nname: [a\n---\n", 2, None, "schema-invalid-yaml", ""),
        ("---\nname: a\n", 1, None, "schema-invalid-yaml", "no closing `---` line"),
    ],
)
def test_invalid_relation_files(
    tmp_path: Path, text: str, line: int | None, field: str | None, code: str, fragment: str
) -> None:
    issues = _vault(tmp_path, {}, {"r": text})
    assert _brief(issues) == [(".knott/relations/r.md", line, field, code)]
    assert fragment in issues[0].message


def test_relation_with_invalid_key_still_loads(tmp_path: Path) -> None:
    _vault(tmp_path, {}, {"r": "---\nname: a\nsymmetric: yes\ninverse: b\n---\n"})
    _, relations, _ = load_ontology(tmp_path)
    assert relations["a"].symmetric is False
    assert relations["a"].inverse == "b"


def test_duplicate_relation_reported_at_second_file(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {},
        {"a": "---\nname: same\n---\n", "b": "---\ndescription: x\nname: same\n---\n"},
    )
    assert _brief(issues) == [(".knott/relations/b.md", 3, "name", "schema-duplicate-relation")]
    assert "`.knott/relations/a.md` and in `.knott/relations/b.md`" in issues[0].message
    _, relations, _ = load_ontology(tmp_path)
    assert relations["same"].path == ".knott/relations/a.md"


def test_relation_and_concept_names_are_separate_namespaces(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {"about": "---\nname: about\n---\n"},
        {"about": "---\nname: about\n---\n"},
    )
    assert issues == []


# --- `relation:` on properties ------------------------------------------------

_REL = {"about": "---\nname: about\n---\n"}


@pytest.mark.parametrize(
    ("properties", "field", "line", "fragment"),
    [
        (
            "  a:\n    type: list\n    relation: about\n    items: {type: reference, target: t}\n",
            "properties.a.relation",
            6,
            "`relation` is not allowed on a list: put `relation:` on `items`",
        ),
        (
            "  a:\n    type: map\n    relation: about\n    values: {type: reference, target: t}\n",
            "properties.a.relation",
            6,
            "`relation` is not allowed on a map: put `relation:` on `values`",
        ),
        (
            "  a: {type: string, relation: about}\n",
            "properties.a.relation",
            4,
            "`relation` is only allowed when `type` is reference, but `type` is string",
        ),
        (
            "  a: {type: reference, target: t, relation: [about]}\n",
            "properties.a.relation",
            4,
            "`relation` must be a relation name, got list",
        ),
    ],
)
def test_misplaced_or_invalid_relation_key(
    tmp_path: Path, properties: str, field: str, line: int, fragment: str
) -> None:
    issues = _vault(tmp_path, {"t": "---\nname: t\nproperties:\n" + properties + "---\n"}, _REL)
    assert [(i.field, i.line, i.code) for i in issues] == [(field, line, "schema-invalid-field")]
    assert fragment in issues[0].message


def test_relation_allowed_on_nested_references(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {
            "t": "---\nname: t\nproperties:\n"
            "  a:\n    type: map\n    values:\n      type: list\n"
            "      items: {type: reference, target: t, relation: about}\n"
            "  b:\n    type: object\n    fields:\n"
            "      c: {type: reference, target: t, relation: about}\n"
            "---\n"
        },
        _REL,
    )
    assert issues == []
    schemas, _, _ = load_ontology(tmp_path)
    shapes = [shape for _, shape in iter_references(schemas["t"])]
    assert [s.relation for s in shapes] == ["about", "about"]


def test_unknown_relation_is_reported_and_reference_still_works(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {
            "t": "---\nname: t\nproperties:\n"
            "  a:\n    type: list\n    items:\n      type: reference\n      target: t\n"
            "      relation: nope\n---\n"
        },
        _REL,
    )
    assert _brief(issues) == [
        (".knott/concepts/t.md", 9, "properties.a.items.relation", "relation-unknown")
    ]
    assert issues[0].message == (
        "`properties.a.items.relation` names relation `nope`, which no relation file in "
        "`.knott/relations/` defines (known relations: `about`); "
        "the reference still works as a plain reference"
    )
    schemas, _, _ = load_ontology(tmp_path)
    shape = schemas["t"].properties["a"].shape
    assert isinstance(shape, ListShape)
    assert shape.items.shape == ReferenceShape(("t",))
    (tmp_path / "x.md").write_text("---\ntype: t\na: [x.md, y.md]\n---\n")
    result = Knott.open(tmp_path).validate(["x.md"])
    assert [i.code for i in result.issues] == ["relation-unknown", "relation-target-not-found"]


def test_many_properties_may_name_one_relation(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {
            "t": "---\nname: t\nproperties:\n"
            "  x: {type: reference, target: u, relation: about}\n"
            "  y: {type: reference, target: u, relation: about}\n---\n",
            "u": "---\nname: u\nproperties:\n"
            "  z: {type: reference, target: t, relation: about}\n---\n",
        },
        _REL,
    )
    assert issues == []


# --- checks on definitions ----------------------------------------------------


def test_two_relations_with_the_same_inverse(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {},
        {
            "a": "---\nname: a\ninverse: back\n---\n",
            "b": "---\nname: b\ninverse: back\n---\n",
        },
    )
    assert _brief(issues) == [(".knott/relations/b.md", 3, "inverse", "relation-inverse-conflict")]
    assert issues[0].message.startswith(
        "relations `a` (`.knott/relations/a.md`) and `b` (`.knott/relations/b.md`) "
        "both declare inverse `back`"
    )


def test_inverse_equals_another_relations_name(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {},
        {"a": "---\nname: a\ninverse: b\n---\n", "b": "---\nname: b\n---\n"},
    )
    assert _brief(issues) == [(".knott/relations/a.md", 3, "inverse", "relation-inverse-conflict")]
    assert "is also the name of relation `b`" in issues[0].message


def test_inverse_equals_own_name_suggests_symmetric(tmp_path: Path) -> None:
    issues = _vault(tmp_path, {}, {"a": "---\nname: a\ninverse: a\n---\n"})
    assert _brief(issues) == [(".knott/relations/a.md", 3, "inverse", "relation-inverse-conflict")]
    assert "use `symmetric: true`" in issues[0].message


def test_inverse_equals_a_property_of_a_target_concept(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {
            "d": "---\nname: d\nproperties:\n"
            "  affects: {type: reference, target: [c, e], relation: about}\n---\n",
            "c": "---\nname: c\nproperties:\n  discussed_in: {type: string}\n---\n",
            "e": "---\nname: e\n---\n",
        },
        {"about": "---\nname: about\ninverse: discussed_in\n---\n"},
    )
    assert _brief(issues) == [
        (".knott/relations/about.md", 3, "inverse", "relation-inverse-conflict")
    ]
    assert "is also a property of concept `c` (`.knott/concepts/c.md`)" in issues[0].message


def test_inverse_may_equal_nested_fields_and_untargeted_properties(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {
            "d": "---\nname: d\nproperties:\n"
            "  affects: {type: reference, target: c, relation: about}\n---\n",
            "c": "---\nname: c\nproperties:\n"
            "  speakers:\n    type: list\n    items:\n      type: object\n"
            "      fields: {discussed_in: {type: string}}\n---\n",
            "g": "---\nname: g\nproperties:\n  discussed_in: {type: string}\n---\n",
        },
        {"about": "---\nname: about\ninverse: discussed_in\n---\n"},
    )
    assert issues == []


def test_unknown_targets_are_not_considered(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {
            "d": "---\nname: d\nproperties:\n"
            "  affects: {type: reference, target: ghost, relation: related}\n---\n",
        },
        {"related": "---\nname: related\nsymmetric: true\n---\n"},
    )
    assert [i.code for i in issues] == ["schema-unknown-target"]


def test_symmetric_with_inverse(tmp_path: Path) -> None:
    issues = _vault(tmp_path, {}, {"a": "---\nname: a\nsymmetric: true\ninverse: b\n---\n"})
    assert _brief(issues) == [
        (".knott/relations/a.md", 4, "inverse", "relation-symmetric-mismatch")
    ]


def test_symmetric_with_acyclic(tmp_path: Path) -> None:
    issues = _vault(tmp_path, {}, {"a": "---\nname: a\nsymmetric: true\nacyclic: true\n---\n"})
    assert _brief(issues) == [
        (".knott/relations/a.md", 4, "acyclic", "relation-symmetric-mismatch")
    ]
    assert "every symmetric link is a two-step loop" in issues[0].message


def test_symmetric_relation_must_be_able_to_point_back(tmp_path: Path) -> None:
    issues = _vault(
        tmp_path,
        {
            "c": "---\nname: c\nproperties:\n"
            "  ok: {type: reference, target: [c, g], relation: related}\n"
            "  bad: {type: reference, target: g, relation: related}\n---\n",
            "g": "---\nname: g\n---\n",
        },
        {"related": "---\nname: related\nsymmetric: true\n---\n"},
    )
    assert _brief(issues) == [
        (".knott/concepts/c.md", 5, "properties.bad.relation", "relation-symmetric-mismatch")
    ]
    assert "don't include its own concept `c`" in issues[0].message


def test_definition_issues_appear_in_validate(tmp_path: Path) -> None:
    _vault(tmp_path, {}, {"a": "---\nname: a\ninverse: a\n---\n"})
    result = Knott.open(tmp_path).validate()
    assert [i.code for i in result.issues] == ["relation-inverse-conflict"]
