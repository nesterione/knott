"""Open reference targets: `target: any` (spec 0014)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from knott import Knott, view
from knott.cli import app
from knott.models import Issue
from knott.schema.loader import load_definitions
from knott.schema.models import ListShape, ReferenceShape
from knott.view import render_ontology

runner = CliRunner()

NOTE = """---
name: note
properties:
  title: { type: string }
  related:
    type: list
    description: Anything worth reading next.
    items: { type: reference, relation: related, target: any }
  promoted_to: { type: reference, target: any }
  about: { type: reference, target: episode }
---
"""
EPISODE = "---\nname: episode\nproperties:\n  notes_count: { type: integer }\n---\n"
RELATED = "---\nname: related\nsymmetric: true\n---\n"


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path, **concepts: str) -> Path:
    root = tmp_path / "vault"
    for name, text in {"note": NOTE, "episode": EPISODE, **concepts}.items():
        _write(root, f".knott/concepts/{name}.md", text)
    _write(root, ".knott/relations/related.md", RELATED)
    return root


def _entity(root: Path, rel: str, frontmatter: str) -> None:
    _write(root, rel, f"---\n{frontmatter}---\n")


def _issues(root: Path) -> list[Issue]:
    return Knott.open(root).validate().issues


def _concept(properties: str) -> str:
    return f"---\nname: note\nproperties:\n{properties}---\n"


# --- concept files -------------------------------------------------------------


def test_open_reference_loads(tmp_path: Path) -> None:
    loaded = load_definitions(_vault(tmp_path))
    assert loaded.issues == []
    properties = loaded.schemas["note"].properties
    promoted = properties["promoted_to"].shape
    assert promoted == ReferenceShape((), open=True)
    related = properties["related"].shape
    assert isinstance(related, ListShape)
    assert related.items.shape == ReferenceShape((), relation="related", open=True)
    about = properties["about"].shape
    assert isinstance(about, ReferenceShape) and not about.open


@pytest.mark.parametrize(
    ("target", "kept", "open_"),
    [
        ("[any, episode]", ("episode",), False),
        ("[episode, any]", ("episode",), False),
        ("[any]", (), False),
    ],
)
def test_any_in_a_list_is_reported_and_the_rest_is_kept(
    tmp_path: Path, target: str, kept: tuple[str, ...], open_: bool
) -> None:
    root = _vault(tmp_path, note=_concept(f"  x: {{ type: reference, target: {target} }}\n"))
    loaded = load_definitions(root)
    assert [(i.code, i.field, i.line) for i in loaded.issues] == [
        ("schema-invalid-field", "properties.x.target", 4)
    ]
    assert "`any` cannot be listed with other targets" in loaded.issues[0].message
    shape = loaded.schemas["note"].properties["x"].shape
    assert isinstance(shape, ReferenceShape)
    assert (shape.targets, shape.open) == (kept, open_)
    _entity(root, "e.md", "type: episode\n")
    _entity(root, "n.md", "type: note\n")
    _entity(root, "a.md", 'type: note\nx: "[e](e.md)"\n')
    _entity(root, "b.md", 'type: note\nx: "[n](n.md)"\n')
    mismatched = [i.path for i in _issues(root) if i.code == "relation-target-type-mismatch"]
    # `[any]` leaves no target, so any entity type passes; otherwise `episode` is enforced.
    assert mismatched == (["b.md"] if kept else [])


@pytest.mark.parametrize("target", ["Any", '"*"', "ANY"])
def test_other_spellings_are_unknown_types(tmp_path: Path, target: str) -> None:
    root = _vault(tmp_path, note=_concept(f"  x: {{ type: reference, target: {target} }}\n"))
    assert [i.code for i in load_definitions(root).issues] == ["schema-unknown-target"]


def test_missing_target_does_not_mean_any(tmp_path: Path) -> None:
    root = _vault(tmp_path, note=_concept("  x: { type: reference }\n"))
    issues = load_definitions(root).issues
    assert [i.code for i in issues] == ["schema-invalid-field"]
    assert "no `target`" in issues[0].message


def test_any_is_a_reserved_type_name(tmp_path: Path) -> None:
    root = _vault(tmp_path, any="---\nname: any\n---\n")
    loaded = load_definitions(root)
    assert [(i.code, i.path, i.field, i.line) for i in loaded.issues] == [
        ("schema-invalid-field", ".knott/concepts/any.md", "name", 2)
    ]
    assert "a concept cannot be named `any`" in loaded.issues[0].message
    assert "any" not in loaded.schemas
    _entity(root, "a.md", "type: any\n")
    assert ("a.md", "entity-unknown-type") in [(i.path, i.code) for i in _issues(root)]


def test_any_cannot_be_a_parent(tmp_path: Path) -> None:
    root = _vault(tmp_path, memo="---\nname: memo\nextends: any\n---\n")
    assert [i.code for i in load_definitions(root).issues] == ["schema-unknown-parent"]


# --- entities ------------------------------------------------------------------


def test_any_entity_passes_the_other_checks_stay(tmp_path: Path) -> None:
    root = _vault(tmp_path, group="---\nname: group\nabstract: true\n---\n")
    _entity(root, "e.md", "type: episode\n")
    _entity(root, "n.md", "type: note\n")
    _entity(root, "g.md", "type: group\n")
    _entity(root, "ghost.md", "type: ghost\n")
    _write(root, "plain.md", "no frontmatter\n")
    _entity(
        root,
        "ok.md",
        'type: note\npromoted_to: "[e](e.md)"\nrelated:\n'
        '  - "[n](n.md)"\n  - "[e](e.md)"\n  - "[ghost](ghost.md)"\n  - "[g](g.md)"\n',
    )
    _entity(
        root,
        "bad.md",
        'type: note\npromoted_to: "[p](plain.md)"\nrelated:\n'
        '  - "[m](missing.md)"\n  - https://example.com\n  - "[o](../outside.md)"\n',
    )
    _entity(root, "typed.md", 'type: note\nabout: "[n](n.md)"\n')
    _entity(root, "shape.md", 'type: note\npromoted_to:\n  - "[e](e.md)"\nrelated: "[e](e.md)"\n')
    assert sorted((i.path, i.field, i.code) for i in _issues(root)) == [
        ("bad.md", "promoted_to", "relation-target-not-entity"),
        ("bad.md", "related[0]", "relation-target-not-found"),
        ("bad.md", "related[1]", "relation-invalid-value"),
        ("bad.md", "related[2]", "relation-target-outside-vault"),
        # The targets carry their own issues; the open reference to them is valid.
        ("g.md", "type", "entity-abstract-type"),
        ("ghost.md", "type", "entity-unknown-type"),
        ("shape.md", "promoted_to", "relation-invalid-value"),
        ("shape.md", "related", "relation-invalid-value"),
        ("typed.md", "about", "relation-target-type-mismatch"),
    ]


def test_required_open_reference(tmp_path: Path) -> None:
    root = _vault(
        tmp_path, note=_concept("  x: { type: reference, target: any, required: true }\n")
    )
    _entity(root, "n.md", "type: note\n")
    assert [(i.field, i.code) for i in _issues(root)] == [("x", "relation-missing")]


def test_refs_and_kid_references_work(tmp_path: Path) -> None:
    root = _vault(tmp_path)
    kid = "11111111-1111-4111-8111-111111111111"
    _entity(root, "e.md", f"type: episode\nkid: {kid}\n")
    _entity(root, "n.md", f'type: note\npromoted_to: kid:{kid}\nrelated:\n  - "[e](e.md)"\n')
    assert _issues(root) == []
    refs = Knott.open(root).refs("e.md")
    assert sorted((g.label, r.path) for g in refs.groups for r in g.references) == [
        ("related", "n.md"),
        ("← note.promoted_to", "n.md"),
    ]


# --- relation and loop checks --------------------------------------------------


def test_symmetric_relation_on_an_open_property_is_valid(tmp_path: Path) -> None:
    assert load_definitions(_vault(tmp_path)).issues == []


def test_inverse_conflicts_with_a_property_of_any_concept(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        note=_concept("  cites: { type: reference, relation: cites, target: any }\n"),
    )
    _write(root, ".knott/relations/cites.md", "---\nname: cites\ninverse: notes_count\n---\n")
    issues = load_definitions(root).issues
    assert [(i.code, i.path) for i in issues] == [
        ("relation-inverse-conflict", ".knott/relations/cites.md")
    ]
    assert "property of concept `episode`" in issues[0].message


def test_loop_inverse_need_is_valid_through_an_open_property(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        episode="---\nname: episode\nproperties:\n"
        "  status: { type: enum, options: [draft, done] }\n---\n",
        note=_concept("  cites: { type: reference, relation: cites, target: any }\n"),
    )
    _write(root, ".knott/relations/cites.md", "---\nname: cites\ninverse: cited_in\n---\n")
    _write(
        root,
        ".knott/loops/flow.md",
        "---\nname: flow\ntype: episode\nproperty: status\nstages:\n  draft:\n"
        "  done: { needs: [cited_in: note] }\n---\n",
    )
    assert load_definitions(root).issues == []
    _entity(root, "a.md", "type: episode\nstatus: done\n")
    _entity(root, "b.md", "type: episode\nstatus: done\n")
    _entity(root, "n.md", 'type: note\ncites: "[a](a.md)"\n')
    assert [(i.path, i.code) for i in _issues(root)] == [("b.md", "loop-stage-unmet")]


# --- CLI, API, view ------------------------------------------------------------


def test_ontology(tmp_path: Path) -> None:
    note = next(t for t in Knott.open(_vault(tmp_path)).ontology().types if t.type == "note")
    by_name = {a.name: a for a in note.properties}
    promoted, related, about = by_name["promoted_to"], by_name["related"], by_name["about"]
    assert (promoted.open, promoted.targets, promoted.unknown_targets) == (True, [], [])
    assert promoted.notation == "reference → any"
    assert related.items is not None and related.items.open
    assert related.notation == "list of reference → any"
    assert (about.open, about.targets) == (False, ["episode"])
    assert [path for path, _ in note.references()] == ["related[]", "promoted_to", "about"]


def test_types_verbose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_vault(tmp_path))
    out = runner.invoke(app, ["types", "--verbose"]).output
    assert (
        "    related      list of reference → any  (related)  Anything worth reading next.\n"
        "    promoted_to  reference → any\n"
        "    about        reference → episode\n"
    ) in out


def _view_data(root: Path) -> dict[str, Any]:
    html = render_ontology(Knott.open(root).ontology())
    start = html.index("const DATA = ") + len("const DATA = ")
    data: dict[str, Any] = json.JSONDecoder().raw_decode(html, start)[0]
    return data


def test_view_data(tmp_path: Path) -> None:
    data = _view_data(_vault(tmp_path, memo="---\nname: memo\nextends: note\n---\n"))
    # No edge for an open reference; the typed one is still drawn.
    assert [(e["source"], e["target"], e["path"]) for e in data["edges"]] == [
        ("note", "episode", "about")
    ]
    # One row per property, at the type that declares it: `memo` only inherits them.
    assert [
        (p["type"], p["path"], p["open"], p["targets"], p["relation"])
        for p in data["reference_properties"]
    ] == [
        ("note", "related[]", True, [], "related"),
        ("note", "promoted_to", True, [], None),
        ("note", "about", False, ["episode"], None),
    ]
    assert [r["type"] for r in data["referenced_by"]] == ["episode"]
    note = next(t for t in data["types"] if t["type"] == "note")
    by_name = {a["name"]: a for a in note["properties"]}
    assert by_name["promoted_to"]["open"] is True
    assert by_name["related"]["items"]["open"] is True
    assert by_name["about"]["open"] is False


def test_view_template_reads_the_open_flag() -> None:
    template = view._template()
    for needle in ("a.open", "p.open", "→ any", "Open references (", "from anywhere"):
        assert needle in template, needle
