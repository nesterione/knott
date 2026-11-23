"""Relations in the ontology API, `knott types --verbose` and `knott view` (spec 0006)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from knott import Knott, Ontology, RelationDefinition, view
from knott.cli import app
from knott.view import ontology_edges, referenced_by, render_ontology

from .conftest import fixture_path

runner = CliRunner()

VAULT = "relation-refs"

VERBOSE = """\
concept  (.knott/concepts/concept.md)
  template: no
  references: related[]
  properties:
    related  list of reference → concept  (related)

decision  (.knott/concepts/decision.md)
  template: no
  references: affects[], supersedes
  properties:
    affects     list of reference → concept  (about)
    supersedes  reference → decision  (supersedes)

guide  (.knott/concepts/guide.md)
  template: no
  references: concepts[], cites[], see
  properties:
    concepts  list of reference → concept
    cites     list of reference → concept  (cites)
    see       reference → guide

issue_code  (.knott/concepts/issue_code.md)
  template: no
  references: about
  properties:
    about  reference → concept  (about)

relations:
  about  inverse: discussed_in
    The source discusses the target.

  cites

  related  symmetric
    The two entities are worth reading together.
    Store the link on either side.

  supersedes  inverse: superseded_by  acyclic
    This entity replaces the target.
    <!-- Use when the old entity is no longer the current answer. -->

    For a partial change, use `amends`.
"""


def _ontology() -> Ontology:
    return Knott.open(fixture_path(VAULT)).ontology()


def _payload(html: str) -> dict[str, Any]:
    start = html.index("const DATA = ") + len("const DATA = ")
    data, _ = json.JSONDecoder().raw_decode(html, start)
    assert isinstance(data, dict)
    return data


# ---------- Python API ----------


def test_ontology_lists_relations_sorted_by_name() -> None:
    relations = _ontology().relations
    assert [r.name for r in relations] == ["about", "cites", "related", "supersedes"]
    assert relations[3] == RelationDefinition(
        name="supersedes",
        description="This entity replaces the target.",
        inverse="superseded_by",
        symmetric=False,
        acyclic=True,
        guidance=(
            "<!-- Use when the old entity is no longer the current answer. -->\n\n"
            "For a partial change, use `amends`.\n"
        ),
        path=".knott/relations/supersedes.md",
    )
    assert relations[1].guidance is None
    assert relations[1].description is None
    assert relations[2].symmetric


def test_ontology_attribute_relation_on_reference_nodes() -> None:
    types = {t.type: t for t in _ontology().types}
    decision = {p.name: p for p in types["decision"].properties}
    assert decision["affects"].relation is None  # the list itself names none
    assert decision["affects"].items is not None
    assert decision["affects"].items.relation == "about"
    assert decision["supersedes"].relation == "supersedes"
    guide = {path: node.relation for path, node in types["guide"].references()}
    # `see` names `mystery`, which no relation file defines: a plain reference
    assert guide == {"concepts[]": None, "cites[]": "cites", "see": None}


def test_ontology_without_relations_folder(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    assert Knott.open(tmp_path).ontology().relations == []


# ---------- knott types --verbose ----------


def test_types_verbose_shows_relations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path(VAULT))
    result = runner.invoke(app, ["types", "--verbose"])
    assert result.exit_code == 1  # `mystery` is relation-unknown
    assert result.stdout == VERBOSE
    assert "relation-unknown" not in result.stdout
    assert "`mystery`" in result.stderr


def test_types_verbose_relation_aligns_descriptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott" / "concepts" / "note.md").write_text(
        "---\nname: note\nproperties:\n"
        "  title: { type: string, description: The title. }\n"
        "  about: { type: reference, target: note, relation: about, description: Topic. }\n"
        "---\n"
    )
    (tmp_path / ".knott" / "relations").mkdir()
    (tmp_path / ".knott" / "relations" / "about.md").write_text("---\nname: about\n---\n")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["types", "--verbose"])
    assert result.exit_code == 0
    assert result.output == (
        "note  (.knott/concepts/note.md)\n"
        "  template: no\n"
        "  references: about\n"
        "  properties:\n"
        "    title  string                     The title.\n"
        "    about  reference → note  (about)  Topic.\n"
        "\n"
        "relations:\n"
        "  about\n"
    )


def test_types_verbose_lists_relations_without_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott" / "relations").mkdir()
    (tmp_path / ".knott" / "relations" / "related.md").write_text(
        "---\nname: related\nsymmetric: true\n---\n"
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["types", "--verbose"])
    assert result.exit_code == 0
    assert result.output == "relations:\n  related  symmetric\n"


def test_types_verbose_without_relations_has_no_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott" / "concepts" / "note.md").write_text("---\nname: note\n---\n")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["types", "--verbose"])
    assert result.output == "note  (.knott/concepts/note.md)\n  template: no\n  references: none\n"


def test_types_plain_lists_types_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path(VAULT))
    result = runner.invoke(app, ["types"])
    assert result.stdout == "concept\ndecision\nguide\nissue_code\n"


# ---------- knott view ----------


def test_view_edges_carry_the_relation() -> None:
    edges = [
        (e["source"], e["target"], e["path"], e["relation"]) for e in ontology_edges(_ontology())
    ]
    assert edges == [
        ("concept", "concept", "related[]", "related"),
        ("decision", "concept", "affects[]", "about"),
        ("decision", "decision", "supersedes", "supersedes"),
        ("guide", "concept", "concepts[]", None),
        ("guide", "concept", "cites[]", "cites"),
        ("guide", "guide", "see", None),
        ("issue_code", "concept", "about", "about"),
    ]


def test_view_referenced_by_uses_refs_groups_and_labels() -> None:
    def ref(type_: str, path: str) -> dict[str, Any]:
        return {"type": type_, "path": path, "required": False}

    assert referenced_by(_ontology()) == [
        {
            "type": "concept",
            "groups": [
                {
                    "label": "discussed_in",
                    "kind": "inverse",
                    "relation": "about",
                    "references": [ref("decision", "affects[]"), ref("issue_code", "about")],
                },
                {
                    "label": "related",
                    "kind": "symmetric",
                    "relation": "related",
                    "references": [ref("concept", "related[]")],
                },
                {
                    "label": "← cites",
                    "kind": "relation",
                    "relation": "cites",
                    "references": [ref("guide", "cites[]")],
                },
                {
                    "label": "← guide.concepts[]",
                    "kind": "property",
                    "relation": None,
                    "references": [ref("guide", "concepts[]")],
                },
            ],
        },
        {
            "type": "decision",
            "groups": [
                {
                    "label": "superseded_by",
                    "kind": "inverse",
                    "relation": "supersedes",
                    "references": [ref("decision", "supersedes")],
                }
            ],
        },
        {
            "type": "guide",
            "groups": [
                {
                    "label": "← guide.see",
                    "kind": "property",
                    "relation": None,
                    "references": [ref("guide", "see")],
                }
            ],
        },
    ]


def test_view_referenced_by_labels_match_refs() -> None:
    """The type-level groups of `concept` carry the labels `knott refs` prints for one."""
    refs = Knott.open(fixture_path(VAULT)).refs("concepts/relation.md")
    by_type = {r["type"]: r["groups"] for r in referenced_by(_ontology())}
    view_groups = [(g["label"], g["kind"], g["relation"]) for g in by_type["concept"]]
    refs_groups = [(g.label, g.kind, g.relation) for g in refs.groups]
    # `guide.see` targets `guide`; the entity lists it only because one guide points
    # at a concept anyway (a wrong-type reference). The type view lists what can point.
    assert view_groups == [g for g in refs_groups if g[0] != "← guide.see"]


def test_view_referenced_by_skips_unknown_targets_and_keeps_required() -> None:
    ontology = Knott.open(fixture_path("union-target")).ontology()
    by_type = {r["type"]: r["groups"] for r in referenced_by(ontology)}
    assert set(by_type) == {"episode", "meeting"}
    assert [g["label"] for g in by_type["episode"]] == ["← note.about", "← note.sources[]"]
    ontology = Knott.open(fixture_path("valid-vault")).ontology()
    required = [
        (r["type"], r["path"], r["required"])
        for entry in referenced_by(ontology)
        for g in entry["groups"]
        for r in g["references"]
    ]
    assert any(req for _, _, req in required)


def test_view_payload_has_relations_and_referenced_by() -> None:
    ontology = _ontology()
    data = _payload(render_ontology(ontology))
    assert data["relations"] == [r.model_dump() for r in ontology.relations]
    assert data["referenced_by"] == referenced_by(ontology)
    assert data["edges"] == ontology_edges(ontology)


def test_view_escapes_hostile_relation_text(tmp_path: Path) -> None:
    hostile = "</script><script>alert(1)</script> <!--<b>x</b>"
    Knott.init(tmp_path)
    (tmp_path / ".knott" / "relations").mkdir()
    (tmp_path / ".knott" / "relations" / "about.md").write_text(
        f"---\nname: about\ndescription: '{hostile}'\n---\n{hostile}\n"
    )
    ontology = Knott.open(tmp_path).ontology()
    html = render_ontology(ontology)
    assert html.count("</script>") == 1
    relation = _payload(html)["relations"][0]
    assert relation["description"] == hostile
    assert relation["guidance"] == hostile + "\n"


def test_view_template_reads_relation_data() -> None:
    """The page reads every relation field and escapes the free text it shows."""
    template = view._template()
    for name in RelationDefinition.model_fields:
        if name == "path":
            continue
        assert re.search(rf"\br\.{name}\b", template), name
    assert "esc(r.description)" in template
    assert "esc(r.guidance)" in template
    assert "esc(r.name)" in template
    assert "esc(g.label)" in template
    for key in ("label", "kind", "references"):
        assert re.search(rf"\bg\.{key}\b", template), key
    for key in ("type", "path", "required"):
        assert re.search(rf"\br\.{key}\b", template), key
    assert re.search(r"DATA\.referenced_by\b", template)
    assert re.search(r"DATA\.relations\b", template)
    assert re.search(r"\ba\.relation\b", template)
    # an edge is labelled with its relation, else its path
    assert "name: d.relation || d.path" in template
