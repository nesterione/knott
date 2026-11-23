from __future__ import annotations

from pathlib import Path

import pytest

from knott import (
    Knott,
    OntologyAttribute,
    PathNotFoundError,
    PathOutsideVaultError,
    VaultNotFoundError,
)

from .conftest import fixture_path


def test_open_walks_up_to_vault_root() -> None:
    vault = Knott.open(fixture_path("valid-vault") / "scripts" / "episode-42.md")
    assert vault.root == fixture_path("valid-vault").resolve()


def test_open_without_vault_raises(tmp_path: Path) -> None:
    with pytest.raises(VaultNotFoundError):
        Knott.open(tmp_path)


def test_validate_paths_relative_to_vault_root() -> None:
    vault = Knott.open(fixture_path("wrong-relation-target-type"))
    assert not vault.validate(["transcripts/foo.md"]).ok
    assert vault.validate(["scripts"]).ok


def test_validate_bad_paths_raise() -> None:
    vault = Knott.open(fixture_path("valid-vault"))
    with pytest.raises(PathNotFoundError):
        vault.validate(["missing.md"])
    with pytest.raises(PathOutsideVaultError):
        vault.validate([fixture_path("unknown-type")])


def test_results_are_plain_frozen_data() -> None:
    result = Knott.open(fixture_path("unknown-type")).validate()
    issue = result.issues[0]
    assert issue.model_dump() == {
        "code": "entity-unknown-type",
        "path": "notes/mystery.md",
        "line": 2,
        "field": "type",
        "message": issue.message,
    }
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError on frozen model
        issue.code = "x"


def test_docs_folder_is_a_valid_vault() -> None:
    """docs/ is written as a Knott vault; keep it valid."""
    docs = Path(__file__).parent.parent / "docs"
    result = Knott.open(docs).validate()
    assert result.ok, result.issues
    assert Knott.open(docs).types() == [
        "command",
        "concept",
        "decision",
        "guide",
        "intent",
        "issue_code",
        "spec",
    ]
    relations = Knott.open(docs).ontology().relations
    assert [r.name for r in relations] == ["about", "amends", "related", "supersedes"]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ontology_vault(root: Path) -> Path:
    root.mkdir()
    Knott.init(root)
    concepts = root / ".knott" / "concepts"
    _write(
        concepts / "person.md",
        "---\n"
        "name: person\n"
        "description: A human.\n"
        "properties:\n"
        "  name:\n"
        "    type: string\n"
        "    required: true\n"
        "    description: Full name.\n"
        "  born:\n"
        "    type: date\n"
        "  manager:\n"
        "    type: reference\n"
        "    target: person\n"
        "  pet:\n"
        "    type: reference\n"
        "    target: animal\n"
        "    description: Missing type.\n"
        "  employer:\n"
        "    type: reference\n"
        "    target: company\n"
        "    required: true\n"
        "---\n",
    )
    _write(concepts / "company.md", "---\nname: company\n---\n")
    _write(root / "people" / "ann.md", "---\ntype: person\nname: Ann\n---\n")
    _write(root / "people" / "bob.md", "---\ntype: person\nname: Bob\n---\n")
    _write(root / "people" / "broken.md", "---\ntype: person\nname: [unclosed\n---\n")
    _write(root / "acme.md", "---\ntype: company\n---\n")
    _write(root / "note.md", "# Just a note\n")
    _write(root / "tagged.md", "---\ntags: [a]\n---\n")
    _write(root / "odd.md", "---\ntype: [person]\n---\n")  # not a type name: not counted
    _write(root / "pets" / "rex.md", "---\ntype: animal\n---\n")  # no schema: no type
    return root


def test_ontology_types_properties_and_counts(tmp_path: Path) -> None:
    ontology = Knott.open(_ontology_vault(tmp_path / "vault")).ontology()

    assert ontology.vault == "vault"
    assert ontology.schema_issues == 1  # schema-unknown-target for `pet`
    assert [t.type for t in ontology.types] == ["company", "person"]
    company, person = ontology.types
    assert company.count == 1
    assert company.properties == []
    assert company.template is None
    assert company.references() == []
    assert person.count == 2  # broken.md (invalid frontmatter) is skipped
    assert person.description == "A human."
    assert person.path == ".knott/concepts/person.md"
    scalar: dict[str, object] = {
        "items": None,
        "values": None,
        "fields": [],
        "targets": [],
        "unknown_targets": [],
        "relation": None,
    }
    assert [a.model_dump() for a in person.properties[:2]] == [
        {"name": "name", "type": "string", "required": True, "description": "Full name.", **scalar},
        {"name": "born", "type": "date", "required": False, "description": None, **scalar},
    ]
    assert [
        (a.name, a.type, a.required, a.targets, a.unknown_targets, a.description)
        for a in person.properties[2:]
    ] == [
        ("manager", "reference", False, ["person"], [], None),
        ("pet", "reference", False, [], ["animal"], "Missing type."),
        ("employer", "reference", True, ["company"], [], None),
    ]
    assert [(path, a.notation) for path, a in person.references()] == [
        ("manager", "reference → person"),
        ("pet", "reference"),
        ("employer", "reference → company"),
    ]


def test_ontology_type_without_entities_has_zero_count(tmp_path: Path) -> None:
    root = _ontology_vault(tmp_path / "vault")
    _write(root / ".knott" / "concepts" / "region.md", "---\nname: region\n---\n")
    ontology = Knott.open(root).ontology()
    assert [(t.type, t.count) for t in ontology.types] == [
        ("company", 1),
        ("person", 2),
        ("region", 0),
    ]


def test_ontology_empty_vault(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    ontology = Knott.open(tmp_path).ontology()
    assert ontology.types == []
    assert ontology.schema_issues == 0


def test_ontology_broken_schema_keeps_other_types(tmp_path: Path) -> None:
    root = _ontology_vault(tmp_path / "vault")
    _write(root / ".knott" / "concepts" / "bad.md", "---\nname: [not, a, name]\n---\n")
    ontology = Knott.open(root).ontology()
    assert ontology.schema_issues > 1
    assert [t.type for t in ontology.types] == ["company", "person"]


def test_ontology_is_json_serialisable(tmp_path: Path) -> None:
    ontology = Knott.open(_ontology_vault(tmp_path / "vault")).ontology()
    assert type(ontology).model_validate_json(ontology.model_dump_json()) == ontology


def test_ontology_mirrors_structured_attributes() -> None:
    ontology = Knott.open(fixture_path("structured-attributes")).ontology()
    (lexeme,) = ontology.types
    by_name = {a.name: a for a in lexeme.properties}
    assert by_name["lemma"] == OntologyAttribute(
        name="lemma", type="string", required=True, description=None
    )
    senses = by_name["senses"]
    assert (senses.type, senses.required, senses.notation) == ("list", True, "list of object")
    assert senses.items == OntologyAttribute(
        name=None,
        type="object",
        required=False,
        description="One sense per meaning.",
        fields=[
            OntologyAttribute(name="id", type="string", required=True, description=None),
            OntologyAttribute(name="ru", type="string", required=True, description="Russian gloss"),
        ],
    )
    forms = by_name["forms"]
    assert forms.notation == "map of map of string"
    assert forms.values is not None and forms.values.values is not None
    assert forms.values.values.type == "string"
    assert [f.name for f in by_name["review"].fields] == ["type", "done"]
    assert type(ontology).model_validate_json(ontology.model_dump_json()) == ontology


def test_ontology_nested_references() -> None:
    ontology = Knott.open(fixture_path("nested-references")).ontology()
    episode = next(t for t in ontology.types if t.type == "episode")
    assert [a.name for a in episode.properties] == ["title", "speakers", "hosts", "production"]
    speakers = episode.properties[1]
    assert speakers.notation == "list of object"
    assert speakers.items is not None
    person = speakers.items.fields[0]
    assert (person.name, person.type, person.required, person.targets) == (
        "person",
        "reference",
        True,
        ["person"],
    )
    assert episode.properties[2].notation == "map of reference → person"
    assert [(path, a.targets) for path, a in episode.references()] == [
        ("speakers[].person", ["person"]),
        ("hosts.*", ["person"]),
        ("production.team", ["team"]),
    ]
    assert episode.template is None


def test_ontology_union_and_unknown_targets() -> None:
    ontology = Knott.open(fixture_path("union-target")).ontology()
    note = next(t for t in ontology.types if t.type == "note")
    refs = {path: a for path, a in note.references()}
    assert list(refs) == ["about", "sources[]", "mystery"]
    assert (refs["about"].targets, refs["about"].unknown_targets) == (["episode", "meeting"], [])
    assert (refs["sources[]"].targets, refs["sources[]"].unknown_targets) == (
        ["episode", "meeting"],
        ["podcast"],
    )
    assert note.properties[1].notation == "list of reference → episode | meeting"
    # every target unknown: the reference stays, with no known targets
    assert (refs["mystery"].targets, refs["mystery"].unknown_targets) == ([], ["podcast", "show"])
    assert refs["mystery"].notation == "reference"
    assert ontology.schema_issues == 3  # podcast (sources), podcast and show (mystery)


def test_ontology_template_is_the_concept_body(tmp_path: Path) -> None:
    concepts = tmp_path / ".knott" / "concepts"
    body = "## Summary\n<!-- One paragraph: what was decided. -->\n\n## Why\n"
    _write(concepts / "decision.md", f"---\nname: decision\n---\n{body}")
    _write(concepts / "blank.md", "---\nname: blank\n---\n\n   \n")
    _write(concepts / "bare.md", "---\nname: bare\n---\n")
    types = {t.type: t for t in Knott.open(tmp_path).ontology().types}
    assert types["decision"].template == body
    assert types["blank"].template is None
    assert types["bare"].template is None
    for t in types.values():
        assert t.properties == []
        assert t.references() == []
    ontology = Knott.open(tmp_path).ontology()
    assert type(ontology).model_validate_json(ontology.model_dump_json()) == ontology
