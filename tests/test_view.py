from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def _embedded(html: str) -> Ontology:
    start = html.index("const DATA = ") + len("const DATA = ")
    data, _ = json.JSONDecoder().raw_decode(html, start)
    return Ontology.model_validate(data)


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
    assert "</script><script>alert(1)" not in html
    assert "<!--" not in html
    assert html.count("</script>") == 1
    assert _embedded(html) == ontology


def test_render_loads_nothing_external() -> None:
    html = render_ontology(_ontology())
    for needle in ('src="http', 'href="http', "src='http", "url(http", "@import", "//cdn"):
        assert needle not in html


def test_render_docs_vault() -> None:
    docs = Path(__file__).parent.parent / "docs"
    ontology = Knott.open(docs).ontology()
    assert _embedded(render_ontology(ontology)) == ontology


def test_render_without_placeholder_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(view, "_template", lambda: "<html></html>")
    with pytest.raises(RuntimeError):
        render_ontology(_ontology())


def test_render_with_duplicate_placeholder_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(view, "_template", lambda: PLACEHOLDER * 2)
    with pytest.raises(RuntimeError):
        render_ontology(_ontology())
