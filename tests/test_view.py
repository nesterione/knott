from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from knott import Knott, Ontology, OntologyAttribute, OntologyRelation, OntologyType, view
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
                path=".knott/schemas/task.yaml",
                count=3,
                attributes=[
                    OntologyAttribute(name="title", type="string", required=True, description=None)
                ],
                relations=[
                    OntologyRelation(
                        name="blocked_by",
                        target="task",
                        required=False,
                        description="Tasks that must finish first.",
                        target_known=True,
                    ),
                    OntologyRelation(
                        name="owner",
                        target="person",
                        required=True,
                        description=None,
                        target_known=False,
                    ),
                ],
            )
        ],
    )


def _json_slice(html: str) -> tuple[int, int]:
    start = html.index("const DATA = ") + len("const DATA = ")
    _, end = json.JSONDecoder().raw_decode(html, start)
    return start, end


def _embedded(html: str) -> Ontology:
    start, end = _json_slice(html)
    return Ontology.model_validate(json.loads(html[start:end]))


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
        Ontology: ["vault", "types", "schema_issues"],
        OntologyType: ["type", "description", "count", "attributes", "relations"],
        OntologyAttribute: ["name", "type", "required", "description"],
        OntologyRelation: ["name", "target", "required", "description", "target_known"],
    }
    for model, names in reads.items():
        for name in names:
            assert name in model.model_fields, (model.__name__, name)
            assert re.search(rf"\.{name}\b", template), (model.__name__, name)


def test_render_docs_vault() -> None:
    docs = Path(__file__).parent.parent / "docs"
    ontology = Knott.open(docs).ontology()
    assert _embedded(render_ontology(ontology)) == ontology


def test_render_without_placeholder_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(view, "_template", lambda: "<html></html>")
    with pytest.raises(RuntimeError):
        render_ontology(_ontology())
