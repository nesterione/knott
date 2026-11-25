from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from knott import Knott, Ontology, OntologyAttribute, OntologyType, view
from knott.view import PLACEHOLDER, render_ontology

HOSTILE = "Ends here </script><script>alert(1)</script> and <!--<script> too."


def _ontology(description: str | None = "A task.") -> Ontology:
    return Ontology(
        vault="notes",
        schema_issues=1,
        types=[
            OntologyType(
                type="task",
                description=description,
                path=".knott/concepts/task.md",
                count=3,
                properties=[
                    OntologyAttribute(name="title", type="string", required=True, description=None),
                    OntologyAttribute(
                        name="blocked_by",
                        type="list",
                        required=False,
                        description="Tasks that must finish first.",
                        items=OntologyAttribute(
                            name=None,
                            type="reference",
                            required=False,
                            description=None,
                            targets=["task"],
                        ),
                    ),
                    OntologyAttribute(
                        name="owner",
                        type="reference",
                        required=True,
                        description=None,
                        unknown_targets=["person"],
                    ),
                ],
                template="## Notes\n<!-- What is left to do. -->\n",
            )
        ],
    )


def _json_slice(html: str) -> tuple[int, int]:
    start = html.index("const DATA = ") + len("const DATA = ")
    _, end = json.JSONDecoder().raw_decode(html, start)
    return start, end


def _payload(html: str) -> dict[str, Any]:
    start, end = _json_slice(html)
    data: dict[str, Any] = json.loads(html[start:end])
    return data


def _embedded(html: str) -> Ontology:
    data = _payload(html)
    data.pop("edges")
    data.pop("referenced_by")
    data.pop("reference_properties")
    data.pop("loop_reports")
    return Ontology.model_validate(data)


def _edges(fixture: str) -> list[tuple[str, str, str, bool]]:
    ontology = Knott.open(Path(__file__).parent / "fixtures" / fixture).ontology()
    edges = _payload(render_ontology(ontology))["edges"]
    return [(e["source"], e["target"], e["path"], e["required"]) for e in edges]


def test_render_replaces_placeholder_with_model_json() -> None:
    ontology = _ontology()
    html = render_ontology(ontology)
    assert PLACEHOLDER not in html
    assert html.startswith("<!doctype html>")
    assert _embedded(html) == ontology


def test_render_keeps_non_ascii_text() -> None:
    ontology = _ontology("Задача — ✓")
    html = render_ontology(ontology)
    assert "Задача — ✓" in html
    assert _embedded(html) == ontology


def test_render_escapes_script_breakouts() -> None:
    ontology = _ontology(HOSTILE)
    html = render_ontology(ontology)
    start, end = _json_slice(html)
    data = html[start:end]
    assert "</" not in data
    assert "<!--" not in data
    assert html.count("</script>") == 1
    assert _embedded(html) == ontology


def test_render_escapes_lone_surrogates() -> None:
    ontology = _ontology("broken \ud800 text")
    html = render_ontology(ontology)
    html.encode("utf-8")  # would raise on a raw lone surrogate
    assert _embedded(html) == ontology


def test_render_loads_nothing_external() -> None:
    html = render_ontology(_ontology())
    urls = re.findall(r"[a-z]+://[^\s\"'`)]*|//[a-z0-9-]+\.[a-z0-9.-]*[a-z]", html, re.IGNORECASE)
    assert urls == ["http://www.w3.org/2000/svg"]
    for needle in ("@import", "fetch(", "import(", "XMLHttpRequest", "WebSocket"):
        assert needle not in html


def test_template_reads_model_fields() -> None:
    """Every model field the page relies on is read in the template, so renames break here."""
    template = view._template()
    reads: dict[type[BaseModel], list[str]] = {
        Ontology: ["vault", "types", "schema_issues", "relations"],
        OntologyType: [
            "type",
            "description",
            "count",
            "kid_required",
            "entity_paths",
            "filename",
            "properties",
            "template",
        ],
        OntologyAttribute: [
            "name",
            "type",
            "required",
            "description",
            "items",
            "values",
            "fields",
            "targets",
            "unknown_targets",
            "relation",
        ],
    }
    for model, names in reads.items():
        for name in names:
            assert name in model.model_fields, (model.__name__, name)
            assert re.search(rf"\.{name}\b", template), (model.__name__, name)
    assert re.search(r"DATA\.edges\b", template)
    edge = view.ontology_edges(_ontology())[0]
    for key in edge:
        assert re.search(rf"\.{key}\b", template), key


def test_render_docs_vault() -> None:
    docs = Path(__file__).parent.parent / "docs"
    ontology = Knott.open(docs).ontology()
    assert _embedded(render_ontology(ontology)) == ontology


def test_render_without_placeholder_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(view, "_template", lambda: "<html></html>")
    with pytest.raises(RuntimeError):
        render_ontology(_ontology())


def test_render_keeps_nested_attribute_shapes() -> None:
    ontology = Knott.open(Path(__file__).parent / "fixtures" / "structured-attributes").ontology()
    embedded = _embedded(render_ontology(ontology))
    assert embedded == ontology
    senses = next(a for a in embedded.types[0].properties if a.name == "senses")
    assert senses.items is not None
    assert [f.name for f in senses.items.fields] == ["id", "ru"]


def test_view_edges_for_nested_references() -> None:
    # one edge per reference, labelled with its path; required only when every step is
    assert _edges("nested-references") == [
        ("episode", "person", "speakers[].person", False),
        ("episode", "person", "hosts.*", False),
        ("episode", "team", "production.team", False),
    ]


def test_view_edges_for_union_targets_skip_unknown_targets() -> None:
    # `podcast` and `show` have no concept: no edge, and `mystery` (all unknown) has none
    assert _edges("union-target") == [
        ("note", "episode", "about", False),
        ("note", "meeting", "about", False),
        ("note", "episode", "sources[]", False),
        ("note", "meeting", "sources[]", False),
    ]


def test_view_edge_required_follows_the_path() -> None:
    ontology = _ontology()
    assert view.ontology_edges(ontology) == [
        {
            "source": "task",
            "target": "task",
            "path": "blocked_by[]",
            "relation": None,
            "required": False,
        }
    ]
    owner = ontology.types[0].properties[2]
    required = ontology.model_copy(
        update={
            "types": [
                ontology.types[0].model_copy(
                    update={"properties": [owner.model_copy(update={"targets": ["task"]})]}
                )
            ]
        }
    )
    assert view.ontology_edges(required) == [
        {"source": "task", "target": "task", "path": "owner", "relation": None, "required": True}
    ]


def test_view_payload_includes_template() -> None:
    html = render_ontology(_ontology())
    assert _payload(html)["types"][0]["template"] == "## Notes\n<!-- What is left to do. -->\n"
    assert "<details>" in html
