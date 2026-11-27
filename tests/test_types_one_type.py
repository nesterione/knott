"""`knott types NAME`: the details of one type (spec 0017)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott.cli import app

from .conftest import FIXTURES

runner = CliRunner()

CONCEPT = """---
name: concept
abstract: true
properties:
  title: { type: string, required: true }
  status: { type: enum, options: [draft, done] }
  related:
    type: list
    items: { type: reference, relation: related, target: concept }
---
# <!-- title -->

Body with a trailing space:\x20

<!-- last line -->
"""
TOOL = """---
name: tool
extends: concept
description: A piece of software.
properties:
  made_by: { type: reference, relation: made, target: concept }
  logo: { type: list, items: { type: object, fields: { image: { type: file } } } }
---
"""
NOTE = "---\nname: note\nproperties:\n  about: { type: reference, target: concept }\n---\n"
TASK = "---\nname: task\nproperties:\n  state: { type: enum, options: [todo, done] }\n---\n"
FILES = {
    ".knott/concepts/concept.md": CONCEPT,
    ".knott/concepts/tool.md": TOOL,
    ".knott/concepts/note.md": NOTE,
    ".knott/concepts/task.md": TASK,
    ".knott/relations/related.md": "---\nname: related\nsymmetric: true\n---\nUse between peers.\n",
    ".knott/relations/made.md": "---\nname: made\ninverse: makes\n---\n",
    ".knott/relations/unused.md": "---\nname: unused\n---\n",
    ".knott/connectors/s3.md": "---\nname: s3\ndescription: A bucket.\n---\n",
    ".knott/loops/review.md": (
        "---\nname: review\ntype: concept\nproperty: status\nstages:\n  draft:\n  done:\n---\n"
    ),
    ".knott/loops/work.md": (
        "---\nname: work\ntype: task\nproperty: state\nstages:\n  todo:\n  done:\n---\n"
    ),
}


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vault"
    for rel, text in FILES.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def _verbose_block(name: str) -> str:
    """The block `knott types --verbose` prints for one type."""
    blocks = runner.invoke(app, ["types", "--verbose"]).output.split("\n\n")
    return next(b for b in blocks if b.startswith(f"{name}  ("))


def test_one_type_with_everything_it_uses(vault: Path) -> None:
    result = runner.invoke(app, ["types", "tool"])
    assert result.exit_code == 0, result.output
    assert result.output == (
        "tool  (.knott/concepts/tool.md)\n"
        "  A piece of software.\n"
        "  extends: concept\n"
        "  template: yes (from concept)\n"
        "  references: related[], made_by\n"
        "  properties (from concept):\n"
        "    title*   string\n"
        "    status   enum\n"
        "      one of: draft | done\n"
        "    related  list of reference → concept  (related)\n"
        "  properties:\n"
        "    made_by  reference → concept  (made)\n"
        "    logo     list of object\n"
        "      image  file\n"
        "  template body:\n"
        "    # <!-- title -->\n"
        "\n"
        "    Body with a trailing space: \n"
        "\n"
        "    <!-- last line -->\n"
        "\n"
        "relations:\n"
        "  made  inverse: makes\n"
        "\n"
        "  related  symmetric\n"
        "    Use between peers.\n"
        "\n"
        "connectors:\n"
        "  s3\n"
        "    A bucket.\n"
        "\n"
        "loops:\n"
        "  review  concept.status\n"
        "    stages: draft → done\n"
    )


def test_block_is_the_verbose_block(vault: Path) -> None:
    for name in ("concept", "tool", "note", "task"):
        assert runner.invoke(app, ["types", name]).output.startswith(_verbose_block(name).rstrip())
    # --verbose is accepted and changes nothing
    plain = runner.invoke(app, ["types", "tool"]).output
    assert runner.invoke(app, ["types", "tool", "--verbose"]).output == plain


def test_sections_are_limited_to_what_the_type_uses(vault: Path) -> None:
    # a relation that only points at the type, a loop of a subtype and connectors
    # without a file property are left out
    concept = runner.invoke(app, ["types", "concept"]).output
    assert "abstract: yes" in concept
    assert "subtypes: tool" in concept
    assert "  related  symmetric" in concept
    assert "made" not in concept.split("relations:")[1]
    assert "connectors:" not in concept
    assert "  review  concept.status" in concept
    assert "tool  (" not in concept  # subtypes are not expanded
    # no relation file, no file property, no loop: the block alone
    note = runner.invoke(app, ["types", "note"]).output
    assert note == _verbose_block("note").rstrip() + "\n"
    task = runner.invoke(app, ["types", "task"]).output
    assert task.endswith("\nloops:\n  work  task.state\n    stages: todo → done\n")
    assert "review" not in task and "relations:" not in task


def test_several_types_share_the_sections(vault: Path) -> None:
    result = runner.invoke(app, ["types", "task", "tool", "task"])
    output = result.output
    assert output.index("task  (") < output.index("tool  (")  # the order given
    assert output.count("task  (.knott") == 1  # a repeated name is printed once
    assert output.count("relations:") == 1 and output.count("loops:") == 1
    assert output.index("  review  concept.status") < output.index("  work  task.state")


def test_unknown_name_is_a_usage_error(vault: Path) -> None:
    result = runner.invoke(app, ["types", "tool", "nope"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        "error: no type named `nope` (known types: `concept`, `note`, `task`, `tool`)\n"
    )
    # the same wording as `knott list`
    assert runner.invoke(app, ["list", "nope"]).stderr == result.stderr


def test_name_cannot_be_combined_with_tree(vault: Path) -> None:
    result = runner.invoke(app, ["types", "tool", "--tree"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "cannot be combined with --tree" in result.stderr


def test_schema_issues_go_to_stderr_after_the_output(vault: Path) -> None:
    (vault / ".knott/concepts/note.md").write_text(
        "---\nname: note\nproperties:\n"
        "  about: { type: reference, relation: ghost, target: concept }\n---\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["types", "note"])
    assert result.exit_code == 1
    assert result.stdout.startswith("note  (.knott/concepts/note.md)\n")
    assert "relations:" not in result.stdout
    assert "relation `ghost`" in result.stderr or "ghost" in result.stderr


def test_legacy_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(FIXTURES / "legacy-layout")
    result = runner.invoke(app, ["types", "script"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("✗ .knott/schemas\n")


def test_without_a_name_nothing_changes(vault: Path) -> None:
    assert runner.invoke(app, ["types"]).output == "concept\nnote\ntask\ntool\n"
    verbose = runner.invoke(app, ["types", "--verbose"]).output
    assert "template body:" not in verbose
    assert "  unused\n" in verbose
