"""`knott types --tree` and the view's Outline (spec 0015)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import view
from knott.cli import app

runner = CliRunner()

RECORD = """---
name: record
abstract: true
description: >
  Anything with a title
  and a date.
properties:
  title: { type: string, required: true }
  created_on: { type: date }
---
"""
DECISION = """---
name: decision
extends: record
path: decisions
description: Why a choice was made.
properties:
  status: { type: string, required: true }
  supersedes: { type: reference, target: decision }
---
"""
SPEC = """---
name: spec
extends: record
path: [specs, "archive/**"]
properties:
  decisions: { type: list, items: { type: reference, target: record } }
---
"""
ADR = "---\nname: adr\nextends: decision\n---\n"
NOTE = "---\nname: note\n---\n"


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path, **concepts: str) -> Path:
    root = tmp_path / "vault"
    for name, text in concepts.items():
        _write(root, f".knott/concepts/{name}.md", text)
    return root


@pytest.fixture
def family(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _vault(tmp_path, record=RECORD, decision=DECISION, spec=SPEC, adr=ADR, note=NOTE)
    for i in range(12):
        _write(root, f"decisions/d{i}.md", f"---\ntype: decision\ntitle: D{i}\nstatus: ok\n---\n")
    _write(root, "specs/s.md", "---\ntype: spec\ntitle: S\n---\n")
    _write(root, "n.md", "---\ntype: note\n---\n")
    monkeypatch.chdir(root)
    return root


def test_tree(family: Path) -> None:
    result = runner.invoke(app, ["types", "--tree"])
    assert result.exit_code == 0
    assert result.output == (
        "note                1\n"
        "record (abstract)\n"
        "├─ decision        12  decisions\n"
        "│  └─ adr           0  decisions\n"
        "└─ spec             1  specs | archive/**\n"
    )


def test_tree_verbose(family: Path) -> None:
    expected = (
        "note                1\n"
        "record (abstract)\n"
        "│  Anything with a title and a date.\n"
        "│  adds: title*, created_on\n"
        "├─ decision        12  decisions\n"
        "│  │  Why a choice was made.\n"
        "│  │  adds: status*, supersedes\n"
        "│  └─ adr           0  decisions\n"
        "└─ spec             1  specs | archive/**\n"
        "      adds: decisions\n"
    )
    for args in (["types", "--tree", "--verbose"], ["types", "-v", "-t"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert result.output == expected


def test_tree_leaves_out_relations_and_other_sections(family: Path) -> None:
    _write(family, ".knott/relations/about.md", "---\nname: about\ndescription: About.\n---\n")
    output = runner.invoke(app, ["types", "--tree", "--verbose"]).output
    assert "relations:" not in output
    assert "relations:" in runner.invoke(app, ["types", "--verbose"]).output


def test_tree_without_inheritance_is_a_flat_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _vault(tmp_path, note=NOTE, task="---\nname: task\npath: tasks\n---\n")
    monkeypatch.chdir(root)
    assert runner.invoke(app, ["types", "--tree"]).output == "note  0\ntask  0  tasks\n"
    # nothing to add with --verbose: neither a description nor own properties
    assert runner.invoke(app, ["types", "--tree", "-v"]).output == "note  0\ntask  0  tasks\n"


def test_tree_abstract_type_has_no_count_even_with_entities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _vault(tmp_path, record="---\nname: record\nabstract: true\npath: records\n---\n")
    _write(root, "records/r.md", "---\ntype: record\n---\n")
    monkeypatch.chdir(root)
    assert runner.invoke(app, ["types", "--tree"]).output == "record (abstract)  records\n"


def test_tree_with_a_broken_parent_lists_the_type_as_a_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _vault(
        tmp_path,
        a="---\nname: a\nextends: b\n---\n",
        b="---\nname: b\nextends: a\n---\n",
        c="---\nname: c\nextends: missing\n---\n",
        d="---\nname: d\nextends: a\n---\n",
    )
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["types", "--tree"])
    assert result.exit_code == 1
    assert result.stdout == "a     0\n└─ d  0\nb     0\nc     0\n"
    assert "schema-extends-cycle" not in result.stdout
    assert "cycle" in result.stderr


def test_tree_of_an_empty_vault_prints_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "vault"
    (root / ".knott" / "concepts").mkdir(parents=True)
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["types", "--tree"])
    assert result.exit_code == 0
    assert result.output == ""


def test_plain_types_is_unchanged(family: Path) -> None:
    assert runner.invoke(app, ["types"]).output == "adr\ndecision\nnote\nrecord\nspec\n"


def test_view_template_has_the_outline() -> None:
    template = view._template()
    assert '<button id="outlineToggle">Outline</button>' in template
    assert '<div id="outline" hidden></div>' in template
    assert "knott-ontology-outline" in template
