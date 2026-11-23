"""`relation-cycle`: loops of an acyclic relation (spec 0006, Cycles)."""

from __future__ import annotations

from pathlib import Path

import pytest

from knott import Knott
from knott.models import Issue
from knott.vault.index import VaultSession
from tests.conftest import fixture_path, validate_fixture

Brief = tuple[str, int | None, str | None, str]


def _brief(issues: list[Issue]) -> list[Brief]:
    return [(i.path, i.line, i.field, i.message.splitlines()[0]) for i in issues]


def _cycles(name: str, paths: list[str] | None = None) -> list[Brief]:
    result = validate_fixture(name, paths)
    return _brief([i for i in result.issues if i.code == "relation-cycle"])


def _msg(relation: str, *chain: str) -> str:
    return f"`{relation}` must not form a cycle: " + " → ".join(chain)


def test_cycles_in_the_fixture_vault() -> None:
    assert _cycles("relation-cycles") == [
        # Path and `kid:` references count the same.
        ("kids/a.md", 4, "supersedes", _msg("supersedes", "kids/a.md", "kids/b.md", "kids/a.md")),
        # Two separate loops are two issues.
        ("pair/a.md", 3, "supersedes", _msg("supersedes", "pair/a.md", "pair/b.md", "pair/a.md")),
        # One loop through two properties naming the same relation is one issue.
        (
            "props/a.md",
            3,
            "supersedes",
            _msg("supersedes", "props/a.md", "props/b.md", "props/a.md"),
        ),
        ("self/a.md", 3, "supersedes", _msg("supersedes", "self/a.md", "self/a.md")),
        (
            "trio/a.md",
            3,
            "supersedes",
            _msg("supersedes", "trio/a.md", "trio/b.md", "trio/c.md", "trio/a.md"),
        ),
    ]


def test_full_fixture_issue_codes() -> None:
    result = validate_fixture("relation-cycles")
    others = [(i.path, i.code) for i in result.issues if i.code != "relation-cycle"]
    # The wrong-type edge doesn't count: the mismatch is reported instead of a cycle.
    assert others == [("wrongtype/a.md", "relation-target-type-mismatch")]


def test_message_has_a_hint() -> None:
    issue = next(i for i in validate_fixture("relation-cycles").issues if i.path == "self/a.md")
    assert issue.message.splitlines()[1] == "remove one of these `supersedes` references"


def test_mixed_relations_and_chains_are_not_cycles() -> None:
    assert _cycles("relation-cycles", ["mixed", "chain", "wrongtype"]) == []


def test_scoped_run_reports_at_first_in_scope_entity_on_the_loop() -> None:
    assert _cycles("relation-cycles", ["trio/c.md", "trio/b.md"]) == [
        (
            "trio/b.md",
            3,
            "supersedes",
            _msg("supersedes", "trio/a.md", "trio/b.md", "trio/c.md", "trio/a.md"),
        ),
    ]


def test_scoped_run_field_is_the_full_property_path() -> None:
    assert _cycles("relation-cycles", ["props/b.md"]) == [
        (
            "props/b.md",
            5,
            "history[1].replaces",
            _msg("supersedes", "props/a.md", "props/b.md", "props/a.md"),
        ),
    ]


def test_scoped_run_out_of_scope_loop_is_not_reported() -> None:
    assert _cycles("relation-cycles", ["props/c.md", "chain"]) == []


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path, relation: str, entities: dict[str, str]) -> Path:
    Knott.init(tmp_path)
    _write(tmp_path, ".knott/relations/r.md", f"---\nname: r\n{relation}---\n")
    _write(
        tmp_path,
        ".knott/concepts/node.md",
        "---\nname: node\nproperties:\n"
        "  next: {type: list, items: {type: reference, target: node, relation: r}}\n---\n",
    )
    for name, targets in entities.items():
        items = "".join(f"  - {t}.md\n" for t in targets.split())
        _write(tmp_path, f"{name}.md", f"---\ntype: node\nnext:\n{items}---\n")
    return tmp_path


def _vault_cycles(root: Path, paths: list[str] | None = None) -> list[Brief]:
    issues = Knott.open(root).validate(paths).issues
    return _brief([i for i in issues if i.code == "relation-cycle"])


def test_loop_is_shortest_from_smallest_path(tmp_path: Path) -> None:
    # a → c → b → a and a → b → a are both loops; the shorter one is named.
    root = _vault(tmp_path, "acyclic: true\n", {"a": "c b", "b": "a", "c": "b"})
    assert _vault_cycles(root) == [("a.md", 5, "next[1]", _msg("r", "a.md", "b.md", "a.md"))]


def test_scoped_component_member_off_the_named_loop(tmp_path: Path) -> None:
    # One component {a, b, c}: the named loop is a → b → a; c is on b → c → b.
    root = _vault(tmp_path, "acyclic: true\n", {"a": "b", "b": "a c", "c": "b"})
    assert _vault_cycles(root) == [("a.md", 4, "next[0]", _msg("r", "a.md", "b.md", "a.md"))]
    assert _vault_cycles(root, ["c.md"]) == [
        ("c.md", 4, "next[0]", _msg("r", "c.md", "b.md", "c.md"))
    ]


def test_non_acyclic_relation_may_loop(tmp_path: Path) -> None:
    root = _vault(tmp_path, "", {"a": "b", "b": "a"})
    assert Knott.open(root).validate().ok


def test_symmetric_acyclic_relation_is_not_cycle_checked(tmp_path: Path) -> None:
    root = _vault(tmp_path, "symmetric: true\nacyclic: true\n", {"a": "b", "b": "a"})
    codes = [i.code for i in Knott.open(root).validate().issues]
    assert codes == ["relation-symmetric-mismatch"]


def test_duplicate_reference_to_the_same_target_is_one_edge(tmp_path: Path) -> None:
    root = _vault(tmp_path, "acyclic: true\n", {"a": "a a"})
    assert _vault_cycles(root) == [("a.md", 4, "next[0]", _msg("r", "a.md", "a.md"))]


def test_graph_is_built_once_when_an_acyclic_relation_is_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    real = VaultSession._entity_references

    def counting(self: VaultSession, rel_path: str):  # type: ignore[no-untyped-def]
        calls.append(rel_path)
        return real(self, rel_path)

    monkeypatch.setattr(VaultSession, "_entity_references", counting)
    Knott.open(fixture_path("relation-cycles")).validate()
    # `amends` and `supersedes` are both checked, on one index built once.
    assert sorted(calls) == sorted(set(calls))
    assert len(calls) == 18
