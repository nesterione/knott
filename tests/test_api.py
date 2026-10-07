from __future__ import annotations

from pathlib import Path

import pytest

from knott import Knott, PathNotFoundError, PathOutsideVaultError, VaultNotFoundError

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
    assert Knott.open(docs).types() == ["command", "concept", "decision", "guide", "issue_code"]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ontology_vault(root: Path) -> Path:
    root.mkdir()
    Knott.init(root)
    schemas = root / ".knott" / "schemas"
    _write(
        schemas / "person.yaml",
        "type: person\n"
        "description: A human.\n"
        "attributes:\n"
        "  name:\n"
        "    type: string\n"
        "    required: true\n"
        "    description: Full name.\n"
        "  born:\n"
        "    type: date\n"
        "relations:\n"
        "  manager:\n"
        "    target: person\n"
        "  pet:\n"
        "    target: animal\n"
        "    description: Missing type.\n"
        "  employer:\n"
        "    target: company\n"
        "    required: true\n",
    )
    _write(schemas / "company.yaml", "type: company\n")
    _write(root / "people" / "ann.md", "---\ntype: person\nname: Ann\n---\n")
    _write(root / "people" / "bob.md", "---\ntype: person\nname: Bob\n---\n")
    _write(root / "people" / "broken.md", "---\ntype: person\nname: [unclosed\n---\n")
    _write(root / "acme.md", "---\ntype: company\n---\n")
    _write(root / "note.md", "# Just a note\n")
    _write(root / "tagged.md", "---\ntags: [a]\n---\n")
    _write(root / "odd.md", "---\ntype: [person]\n---\n")  # not a type name: not counted
    _write(root / "pets" / "rex.md", "---\ntype: animal\n---\n")  # no schema: no type
    return root


def test_ontology_types_relations_and_counts(tmp_path: Path) -> None:
    ontology = Knott.open(_ontology_vault(tmp_path / "vault")).ontology()

    assert ontology.vault == "vault"
    assert ontology.schema_issues == 1  # schema-unknown-target for `pet`
    assert [t.type for t in ontology.types] == ["company", "person"]
    company, person = ontology.types
    assert company.count == 1
    assert company.attributes == []
    assert company.relations == []
    assert person.count == 2  # broken.md (invalid frontmatter) is skipped
    assert person.description == "A human."
    assert person.path == ".knott/schemas/person.yaml"
    assert [a.model_dump() for a in person.attributes] == [
        {"name": "name", "type": "string", "required": True, "description": "Full name."},
        {"name": "born", "type": "date", "required": False, "description": None},
    ]
    assert [(r.name, r.target, r.required, r.target_known) for r in person.relations] == [
        ("manager", "person", False, True),
        ("employer", "company", True, True),
        ("pet", "animal", False, False),
    ]
    assert person.relations[2].description == "Missing type."


def test_ontology_type_without_entities_has_zero_count(tmp_path: Path) -> None:
    root = _ontology_vault(tmp_path / "vault")
    _write(root / ".knott" / "schemas" / "region.yaml", "type: region\n")
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
    _write(root / ".knott" / "schemas" / "bad.yaml", "type: [not, a, name]\n")
    ontology = Knott.open(root).ontology()
    assert ontology.schema_issues > 1
    assert [t.type for t in ontology.types] == ["company", "person"]


def test_ontology_is_json_serialisable(tmp_path: Path) -> None:
    ontology = Knott.open(_ontology_vault(tmp_path / "vault")).ontology()
    assert type(ontology).model_validate_json(ontology.model_dump_json()) == ontology
