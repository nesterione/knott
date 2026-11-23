"""The vault reference index shared by cycle checks and reverse lookup (spec 0006)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from knott import Knott
from knott.schema.loader import load_schemas
from knott.vault import index as index_module
from knott.vault.index import IndexedReference, VaultSession
from tests.conftest import fixture_path

Row = tuple[str, str, str, int | None, str | None, str, bool]


def _session() -> VaultSession:
    root = fixture_path("reference-index")
    schemas, _ = load_schemas(root)
    return VaultSession(root, schemas)


def _rows(refs: list[IndexedReference] | tuple[IndexedReference, ...]) -> list[Row]:
    return [
        (r.source, r.field, r.property_path, r.line, r.relation, r.target, r.type_ok) for r in refs
    ]


def test_every_resolved_reference_is_indexed() -> None:
    assert _rows(_session().references().references) == [
        ("notes/a.md", "about", "about", 4, "about", "topics/home.md", True),
        ("notes/a.md", "related[0]", "related[]", 6, "related", "notes/b.md", True),
        # Nested in a list of objects; the second is a `kid:` reference.
        (
            "notes/a.md",
            "history[0].replaces",
            "history[].replaces",
            9,
            "supersedes",
            "notes/b.md",
            True,
        ),
        (
            "notes/a.md",
            "history[1].replaces",
            "history[].replaces",
            10,
            "supersedes",
            "notes/b.md",
            True,
        ),
        ("notes/a.md", "roles.author", "roles.*", 12, None, "people/ada.md", True),
        # A wrong target type is still indexed, flagged.
        ("notes/a.md", "see", "see", 14, None, "people/ada.md", False),
        ("notes/b.md", "about", "about", 4, "about", "topics/garden.md", True),
        ("notes/b.md", "related[0]", "related[]", 5, "related", "notes/a.md", True),
        ("topics/garden.md", "parent", "parent", 3, None, "topics/home.md", True),
    ]


def test_skipped_references() -> None:
    sources = {r.source for r in _session().references().references}
    # Invalid frontmatter, an unknown type, and values of the wrong kind add nothing.
    assert sources.isdisjoint({"notes/broken.md", "notes/stranger.md", "notes/wrong-kind.md"})
    fields = {(r.source, r.field) for r in _session().references().references}
    # Unresolved (`related[1]`, `roles.editor`), non-entity target (b `see`),
    # and an undeclared key that looks like a path.
    assert ("notes/a.md", "related[1]") not in fields
    assert ("notes/a.md", "roles.editor") not in fields
    assert ("notes/b.md", "see") not in fields
    assert ("notes/a.md", "undeclared") not in fields


def test_indexed_reference_details() -> None:
    see = next(r for r in _session().references().from_("notes/a.md") if r.field == "see")
    assert see == IndexedReference(
        source="notes/a.md",
        source_type="note",
        key_path=("see",),
        field="see",
        property_path="see",
        line=14,
        relation=None,
        target="people/ada.md",
        target_type="person",
        type_ok=False,
    )


def test_lookups_by_target_source_and_relation() -> None:
    index = _session().references()
    assert [(r.source, r.field) for r in index.to("notes/b.md")] == [
        ("notes/a.md", "related[0]"),
        ("notes/a.md", "history[0].replaces"),
        ("notes/a.md", "history[1].replaces"),
    ]
    assert [r.field for r in index.to("topics/home.md")] == ["about", "parent"]
    assert index.to("people/nobody.md") == []
    assert [r.target for r in index.from_("notes/b.md")] == ["topics/garden.md", "notes/a.md"]
    assert index.from_("notes/broken.md") == []
    assert [(r.source, r.field) for r in index.with_relation("supersedes")] == [
        ("notes/a.md", "history[0].replaces"),
        ("notes/a.md", "history[1].replaces"),
    ]
    assert [r.source for r in index.with_relation("related")] == ["notes/a.md", "notes/b.md"]
    assert index.with_relation("unknown") == []


def test_index_is_built_once_per_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    calls: list[str] = []
    real = index_module.VaultSession._entity_references

    def counting(self: VaultSession, rel_path: str):  # type: ignore[no-untyped-def]
        calls.append(rel_path)
        return real(self, rel_path)

    monkeypatch.setattr(VaultSession, "_entity_references", counting)
    first = session.references()
    assert session.references() is first
    assert len(calls) == len(session.all_markdown)


def test_validate_does_not_build_the_index_without_acyclic_relations(
    monkeypatch: pytest.MonkeyPatch, copy_fixture: Callable[[str], Path]
) -> None:
    root = copy_fixture("reference-index")
    (root / ".knott/relations/supersedes.md").write_text(
        "---\nname: supersedes\ninverse: superseded_by\n---\n", encoding="utf-8"
    )

    def fail(self: VaultSession) -> None:
        raise AssertionError("index built")

    monkeypatch.setattr(VaultSession, "references", fail)
    result = Knott.open(root).validate()
    assert result.stats.relations == 8  # all indexed references but the wrong-type `see`
