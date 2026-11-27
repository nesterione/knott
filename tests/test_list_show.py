"""`knott list`, `knott show`, `Knott.entities()` and `Knott.show()` (spec 0016)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from knott import EntityDetail, EntityRecord, Knott, KnottError, OutgoingRef
from knott.cli import app

from .conftest import FIXTURES

runner = CliRunner()

K1 = "11111111-1111-4111-8111-111111111111"
K2 = "22222222-2222-4222-8222-222222222222"

PAGE = "---\nname: page\nabstract: true\nproperties:\n  title: { type: string }\n---\n"
CONCEPT = """---
name: concept
extends: page
properties:
  related:
    type: list
    items: { type: reference, relation: related, target: concept }
---
"""
TOOL = "---\nname: tool\nextends: concept\nproperties:\n  version: { type: string }\n---\n"
RELATED = "---\nname: related\nsymmetric: true\n---\n"
TASK = """---
name: task
properties:
  title: { type: string }
  code: { type: string }
  status: { type: enum, options: [todo, done] }
  points: { type: integer }
  score: { type: number }
  urgent: { type: boolean }
  due: { type: date }
  at: { type: datetime }
  tags: { type: list, items: { type: string } }
  attachment: { type: file }
  about: { type: reference, target: page }
  affects: { type: list, items: { type: reference, target: concept } }
  steps:
    type: list
    items: { type: object, fields: { who: { type: reference, target: concept } } }
  roles: { type: map, values: { type: reference, target: concept } }
  meta: { type: map, values: { type: string } }
---
"""


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vault"
    for name, text in {"page": PAGE, "concept": CONCEPT, "tool": TOOL, "task": TASK}.items():
        _write(root, f".knott/concepts/{name}.md", text)
    _write(root, ".knott/relations/related.md", RELATED)
    _write(root, "concepts/a.md", f"---\ntype: concept\nkid: {K1}\ntitle: A\n---\nBody of A.\n")
    _write(
        root,
        "concepts/b.md",
        '---\ntype: concept\ntitle: B\nrelated:\n  - "[A](a.md)"\n---\n\n',
    )
    _write(root, "concepts/git.md", '---\ntype: tool\ntitle: Git\nversion: "2"\n---\n')
    _write(root, "concepts/hg.md", "---\ntype: tool\ntitle: Hg\nversion: 2\n---\n")
    _write(root, "notes/plain.md", "No frontmatter.\n")
    _write(root, "notes/broken.md", "---\ntype: [\n---\n")
    _write(root, "notes/odd.md", "---\ntype: 42\n---\n")
    _write(root, "notes/unknown.md", "---\ntype: ghost\nrelated: [../concepts/a.md]\n---\n")
    _write(
        root,
        "tasks/one.md",
        f"""---
type: task
title: "a=b"
code: "42"
status: todo
points: 3
score: 3.0
urgent: true
due: 2026-10-06
at: 2026-10-06T09:30:00
tags: [red, blue]
attachment: files/x.pdf
about: ../concepts/git.md
affects:
  - "kid:{K1}"
  - ../concepts/b.md
steps:
  - who: ../concepts/a.md
  - who: ../concepts/missing.md
roles:
  lead: ../notes/plain.md
---
""",
    )
    _write(
        root,
        "tasks/two.md",
        """---
type: task
title: |
  Two
  lines
code: 42
status: done
points: "3"
score: 3
urgent: yes
due: "2026-10-06"
at: 2026-10-06T09:30:00+02:00
tags: []
about: "[[wiki]]"
affects: ../concepts/a.md
roles: {}
meta: {}
extra: [1, {k: v}]
---
""",
    )
    _write(
        root,
        "tasks/three.md",
        "---\ntype: task\ntitle:\naffects:\n  - ../concepts/a.md\n  -\n---\n",
    )
    monkeypatch.chdir(root)
    return root


def _paths(records: list[EntityRecord]) -> list[str]:
    return [r.path for r in records]


def _list(*args: str) -> list[str]:
    result = runner.invoke(app, ["list", *args])
    assert result.exit_code == 0, result.output
    return [line.split()[0] for line in result.output.splitlines()]


def _fails(*args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 2, result.output
    assert result.stdout == ""
    return result.stderr


# --- list: which entities --------------------------------------------------------


def test_list_every_entity_by_path(vault: Path) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert result.output == (
        "concepts/a.md     concept\n"
        "concepts/b.md     concept\n"
        "concepts/git.md   tool\n"
        "concepts/hg.md    tool\n"
        "notes/odd.md      42\n"
        "notes/unknown.md  ghost\n"
        "tasks/one.md      task\n"
        "tasks/three.md    task\n"
        "tasks/two.md      task\n"
    )


def test_list_type_includes_subtypes_and_abstract_parents(vault: Path) -> None:
    assert _list("tool") == ["concepts/git.md", "concepts/hg.md"]
    both = ["concepts/a.md", "concepts/b.md", "concepts/git.md", "concepts/hg.md"]
    assert _list("concept") == both
    assert _list("page") == both


def test_list_unknown_type_is_a_usage_error(vault: Path) -> None:
    assert "known types: `concept`, `page`, `task`, `tool`" in _fails("list", "ghost")
    assert "no type named `42`" in _fails("list", "42")


def test_list_no_match(vault: Path) -> None:
    result = runner.invoke(app, ["list", "task", "--where", "status=done", "--where", "points=3"])
    assert result.exit_code == 0
    assert result.output == "no entities\n"
    result = runner.invoke(app, ["list", "task", "--where", "points=9", "--format", "json"])
    assert json.loads(result.output) == {"entities": []}


# --- list: filters ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("where", "expected"),
    [
        ("code=42", ["tasks/one.md"]),  # a string is never interpreted
        ("title=a=b", ["tasks/one.md"]),  # split at the first `=`
        ("status=done", ["tasks/two.md"]),
        ("points=3", ["tasks/one.md"]),  # not "3"
        ("score=3", ["tasks/one.md", "tasks/two.md"]),  # 3.0 and 3
        ("score=3.0", ["tasks/one.md", "tasks/two.md"]),
        ("urgent=true", ["tasks/one.md"]),  # `yes` is not a boolean spelling
        ("due=2026-10-06", ["tasks/one.md", "tasks/two.md"]),  # a quoted ISO date counts
        ("at=2026-10-06T09:30:00", ["tasks/one.md"]),
        ("at=2026-10-06T07:30:00Z", ["tasks/two.md"]),  # the same moment
        ("tags=blue", ["tasks/one.md"]),
        ("attachment=files/x.pdf", ["tasks/one.md"]),
        ("about=concepts/git.md", ["tasks/one.md"]),
        ("affects=concepts/a.md", ["tasks/one.md", "tasks/three.md"]),  # stored as a kid in one
        (f"affects=kid:{K1}", ["tasks/one.md", "tasks/three.md"]),
        ("affects=concepts/b.md", ["tasks/one.md"]),
        # absent: missing, null, "" and an empty container of the declared kind
        ("title=", ["tasks/three.md"]),
        ("tags=", ["tasks/three.md", "tasks/two.md"]),
        ("about=", ["tasks/three.md"]),
        ("steps=", ["tasks/three.md", "tasks/two.md"]),
        ("roles=", ["tasks/three.md", "tasks/two.md"]),
    ],
)
def test_where(vault: Path, where: str, expected: list[str]) -> None:
    assert _list("task", "--where", where) == expected


def test_where_combines_conditions(vault: Path) -> None:
    assert _list("task", "--where", "score=3", "--where", "status=todo") == ["tasks/one.md"]
    # one key twice: both items on a list, nothing on a scalar
    assert _list("task", "--where", "tags=red", "--where", "tags=blue") == ["tasks/one.md"]
    assert _list("task", "--where", "status=todo", "--where", "status=done") == ["no"]


def test_where_on_a_subtype_property(vault: Path) -> None:
    assert _list("tool", "--where", "version=2") == ["concepts/git.md"]
    error = _fails("list", "concept", "--where", "version=2")
    assert "`version` is not a property of `concept`" in error
    assert "`title`, `related`" in error
    # an inherited property filters every subtype
    assert _list("page", "--where", "title=Git") == ["concepts/git.md"]


def test_where_reference_path_is_relative_to_the_current_directory(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(vault / "concepts")
    assert _list("task", "--where", "affects=b.md") == ["tasks/one.md"]


@pytest.mark.parametrize(
    ("where", "message"),
    [
        ("status=drafted", "expected one of `todo`, `done`"),
        ("status=Todo", "expected one of `todo`, `done`"),
        ("points=many", "expected an integer"),
        ("points=3.0", "expected an integer"),
        ("points=+3", "expected an integer"),
        ("score=nan", "expected a number"),
        ("score=1_000", "expected a number"),
        ("urgent=yes", "expected true or false"),
        ("due=tomorrow", "expected a date"),
        ("due=2026-13-45", "expected a date"),
        ("at=2026-10-06", "expected a datetime"),
        ("about=notes/plain.md", "not a Knott entity"),
        ("about=nowhere.md", "path does not exist"),
        ("about=kid:nope", "kid"),
        (f"about=kid:{K2}", "no entity has `kid`"),
        ("steps=x", "cannot be filtered"),
        ("meta=x", "cannot be filtered"),
        ("nope=1", "`nope` is not a property of `task`"),
        ("status", "expected KEY=VALUE"),
    ],
)
def test_where_usage_errors(vault: Path, where: str, message: str) -> None:
    assert message in _fails("list", "task", "--where", where)


def test_where_needs_a_type(vault: Path) -> None:
    assert "a filter needs a type" in _fails("list", "--where", "status=todo")


# --- list: fields and output -----------------------------------------------------


def test_fields_text(vault: Path) -> None:
    result = runner.invoke(
        app, ["list", "task", "--fields", "title,points,urgent,due,at,tags,extra,nope"]
    )
    assert result.exit_code == 0
    assert result.output == (
        "tasks/one.md    task  a=b        3  true  2026-10-06  2026-10-06T09:30:00        "
        '["red", "blue"]  -                -\n'
        "tasks/three.md  task  -          -  -     -           -                          "
        "-                -                -\n"
        "tasks/two.md    task  Two lines  3  true  2026-10-06  2026-10-06T09:30:00+02:00  "
        '[]               [1, {"k": "v"}]  -\n'
    )


def test_fields_json(vault: Path) -> None:
    result = runner.invoke(
        app, ["list", "tool", "--fields", "version, title,nope", "--format", "json"]
    )
    assert json.loads(result.output) == {
        "entities": [
            {
                "path": "concepts/git.md",
                "type": "tool",
                "kid": None,
                "properties": {"version": "2", "title": "Git", "nope": None},
            },
            {
                "path": "concepts/hg.md",
                "type": "tool",
                "kid": None,
                "properties": {"version": 2, "title": "Hg", "nope": None},
            },
        ]
    }
    # without --fields there is no `properties` key; `kid` is always there
    plain = json.loads(runner.invoke(app, ["list", "concept", "--format", "json"]).output)
    assert plain["entities"][0] == {"path": "concepts/a.md", "type": "concept", "kid": K1}


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ("title,type", "`type`"),
        ("kid", "`kid`"),
        ("path", "`path`"),
        ("a,,b", "empty"),
        ("a,a", "twice"),
    ],
)
def test_fields_usage_errors(vault: Path, fields: str, message: str) -> None:
    assert message in _fails("list", "--fields", fields)


def test_values_json_cannot_hold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "vault"
    _write(root, ".knott/concepts/thing.md", "---\nname: thing\n---\n")
    _write(
        root,
        "t.md",
        "---\ntype: thing\nn: .nan\ni: -.inf\nb: !!binary aGVsbG8=\ns: !!set {x}\n"
        'm: {1: one, 2.5: two}\nblank: ""\nnested: {deep: ["", .inf]}\n'
        "at: 2026-10-06T09:30:00Z\n---\n",
    )
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["show", "t.md", "--format", "json"])
    assert result.exit_code == 0, result.output
    properties = json.loads(result.output)["entity"]["properties"]
    assert properties["n"] == ".nan"
    assert properties["i"] == "-.inf"
    assert "binary" in properties["b"]
    assert "set" in properties["s"]
    assert properties["m"] == {"1": "one", "2.5": "two"}
    assert properties["blank"] is None
    assert properties["nested"] == {"deep": [None, ".inf"]}
    assert properties["at"] == "2026-10-06T09:30:00+00:00"
    assert runner.invoke(app, ["show", "t.md"]).exit_code == 0
    assert runner.invoke(app, ["list", "--fields", "n,b,s,m,at"]).exit_code == 0


# --- show ------------------------------------------------------------------------


def test_show_text(vault: Path) -> None:
    result = runner.invoke(app, ["show", "tasks/one.md"])
    assert result.exit_code == 0
    assert result.output == (
        "tasks/one.md  task\n"
        "\n"
        "properties\n"
        "  title       a=b\n"
        "  code        42\n"
        "  status      todo\n"
        "  points      3\n"
        "  score       3.0\n"
        "  urgent      true\n"
        "  due         2026-10-06\n"
        "  at          2026-10-06T09:30:00\n"
        '  tags        ["red", "blue"]\n'
        "  attachment  files/x.pdf\n"
        '  steps       [{"who": "../concepts/a.md"}, {"who": "../concepts/missing.md"}]\n'
        '  roles       {"lead": "../notes/plain.md"}\n'
        "\n"
        "references\n"
        "  about         concepts/git.md         tool\n"
        "  affects[0]    concepts/a.md           concept\n"
        "  affects[1]    concepts/b.md           concept\n"
        "  steps[0].who  concepts/a.md           concept\n"
        "  steps[1].who  ../concepts/missing.md  relation-target-not-found\n"
        "  roles.lead    notes/plain.md          relation-target-not-entity\n"
    )


def test_show_header_kid_relation_and_referenced_by(vault: Path) -> None:
    result = runner.invoke(app, ["show", "concepts/a.md"])
    assert result.output == (
        f"concepts/a.md  concept  kid:{K1}\n"
        "\n"
        "properties\n"
        "  title  A\n"
        "\n"
        "referenced by\n"
        "  related\n"
        "    concepts/b.md  concept  related[0]  ←\n"
        "\n"
        "  ← task.affects[]\n"
        "    tasks/one.md    task  affects[0]\n"
        "    tasks/three.md  task  affects[0]\n"
        "\n"
        "  ← task.steps[].who\n"
        "    tasks/one.md  task  steps[0].who\n"
    )
    # a symmetric link this entity stores: in `references`, and `out` in its group
    result = runner.invoke(app, ["show", "concepts/b.md"])
    assert "references\n  related[0]  concepts/a.md  concept  (related)\n" in result.output
    assert "  related\n    concepts/a.md  concept  related[0]  →\n" in result.output
    assert runner.invoke(app, ["show", f"kid:{K1}"]).output.startswith("concepts/a.md  concept")


def test_show_malformed_references(vault: Path) -> None:
    detail = Knott.open(vault).show("tasks/two.md")
    assert [(r.field, r.value, r.path, r.error) for r in detail.references] == [
        ("about", "[[wiki]]", None, "relation-invalid-value"),
        # one value where a list is declared: a single row for the property
        ("affects", "../concepts/a.md", None, "relation-invalid-value"),
    ]
    text = runner.invoke(app, ["show", "tasks/two.md"]).output
    assert "  about    [[wiki]]          relation-invalid-value\n" in text
    assert "  affects  ../concepts/a.md  relation-invalid-value\n" in text
    # an empty list item is malformed, as `validate` says
    three = Knott.open(vault).show("tasks/three.md")
    assert [(r.field, r.value, r.error) for r in three.references] == [
        ("affects[0]", "../concepts/a.md", None),
        ("affects[1]", None, "relation-invalid-value"),
    ]


def test_show_wrong_type_target(vault: Path) -> None:
    _write(vault, "tasks/four.md", "---\ntype: task\naffects: [one.md]\n---\n")
    detail = Knott.open(vault).show("tasks/four.md")
    assert detail.references == [
        OutgoingRef(
            field="affects[0]",
            relation=None,
            value="one.md",
            path="tasks/one.md",
            type="task",
            kid=None,
            error="relation-target-type-mismatch",
        )
    ]
    text = runner.invoke(app, ["show", "tasks/four.md"]).output
    assert "  affects[0]  tasks/one.md  task  relation-target-type-mismatch\n" in text


def test_show_unknown_type_has_no_references_but_incoming_links(vault: Path) -> None:
    _write(vault, "concepts/c.md", "---\ntype: concept\nrelated: [../notes/unknown.md]\n---\n")
    detail = Knott.open(vault).show("notes/unknown.md")
    assert detail.entity.type == "ghost"
    assert detail.entity.properties == {"related": ["../concepts/a.md"]}
    assert detail.references == []
    assert [g.label for g in detail.referenced_by] == ["related"]
    assert runner.invoke(app, ["show", "notes/odd.md"]).output == "notes/odd.md  42\n"


def test_show_body(vault: Path) -> None:
    result = runner.invoke(app, ["show", "concepts/a.md", "--body"])
    assert result.output.endswith("    tasks/one.md  task  steps[0].who\n\nbody\nBody of A.\n\n")
    data = json.loads(
        runner.invoke(app, ["show", "concepts/a.md", "--body", "--format", "json"]).output
    )
    assert data["body"] == "Body of A.\n"
    assert "body" not in json.loads(
        runner.invoke(app, ["show", "concepts/a.md", "--format", "json"]).output
    )
    # a blank body: no section, null in JSON
    assert "body" not in runner.invoke(app, ["show", "concepts/b.md", "--body"]).output
    blank = json.loads(
        runner.invoke(app, ["show", "concepts/b.md", "--body", "--format", "json"]).output
    )
    assert blank["body"] is None


def test_show_json(vault: Path) -> None:
    data = json.loads(runner.invoke(app, ["show", "concepts/b.md", "--format", "json"]).output)
    related, affects = data.pop("referenced_by")
    assert affects["label"] == "← task.affects[]"
    assert data == {
        "entity": {
            "path": "concepts/b.md",
            "type": "concept",
            "kid": None,
            "properties": {"title": "B", "related": ["[A](a.md)"]},
        },
        "references": [
            {
                "field": "related[0]",
                "relation": "related",
                "value": "[A](a.md)",
                "path": "concepts/a.md",
                "type": "concept",
                "kid": K1,
                "error": None,
            }
        ],
    }
    assert related == {
        "label": "related",
        "kind": "symmetric",
        "relation": "related",
        "references": [
            {
                "path": "concepts/a.md",
                "type": "concept",
                "kid": K1,
                "field": "related[0]",
                "line": 5,
                "direction": "out",
            }
        ],
    }
    refs = json.loads(runner.invoke(app, ["refs", "concepts/b.md", "--format", "json"]).output)
    assert [related, affects] == refs["groups"]


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("notes/broken.md", "cannot read the frontmatter"),
        ("notes/plain.md", "not a Knott entity"),
        ("notes/nowhere.md", "path does not exist"),
        ("kid:nope", "kid"),
        (f"kid:{K2}", "no entity has `kid`"),
    ],
)
def test_show_usage_errors(vault: Path, path: str, message: str) -> None:
    assert message in _fails("show", path)


def test_legacy_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(FIXTURES / "legacy-layout")
    entity = next(p for p in sorted(Path().rglob("*.md")) if ".knott" not in p.parts)
    for args in (["list"], ["list", "script"], ["show", str(entity)]):
        result = runner.invoke(app, args)
        assert result.exit_code == 1, args
        assert result.stdout == ""
        assert result.stderr.startswith("✗ .knott/schemas\n")


def test_commands_write_nothing(vault: Path) -> None:
    before = {p: p.read_bytes() for p in vault.rglob("*") if p.is_file()}
    runner.invoke(app, ["list", "task", "--fields", "title"])
    runner.invoke(app, ["show", "tasks/one.md", "--body"])
    assert {p: p.read_bytes() for p in vault.rglob("*") if p.is_file()} == before


# --- agreement with validate and refs ---------------------------------------------

REFERENCE_CODES = {
    "relation-invalid-value",
    "relation-target-not-found",
    "relation-target-outside-vault",
    "relation-target-ambiguous",
    "relation-target-not-entity",
    "relation-target-type-mismatch",
}


def _vaults() -> list[Path]:
    roots = [p for p in sorted(FIXTURES.iterdir()) if (p / ".knott" / "concepts").is_dir()]
    return [*roots, FIXTURES.parent.parent / "docs"]


@pytest.mark.parametrize("root", _vaults(), ids=lambda p: p.name)
def test_show_reports_what_validate_reports(root: Path) -> None:
    """Each outgoing reference carries the code `validate` gives that value, and the
    incoming links are those of `refs`."""
    knott = Knott.open(root)
    expected: dict[str, list[tuple[str | None, str]]] = {}
    for issue in knott.validate().issues:
        if issue.code in REFERENCE_CODES:
            expected.setdefault(issue.path, []).append((issue.field, issue.code))
    # `show` loads the vault each time: a sample is enough for the large docs vault
    step = 8 if root.name == "docs" else 1
    for record in knott.entities()[::step]:
        detail = knott.show(record.path)
        errors = [(r.field, r.error) for r in detail.references if r.error is not None]
        assert sorted(errors) == sorted(expected.get(record.path, [])), record.path
        assert detail.referenced_by == knott.refs(record.path).groups
        assert detail.entity.path == record.path
        json.dumps(detail.model_dump(mode="json"), allow_nan=False)


# --- Python API ------------------------------------------------------------------


def test_entities_api(vault: Path) -> None:
    knott = Knott.open(vault)
    assert all(r.properties is None for r in knott.entities())
    assert _paths(knott.entities("tool")) == ["concepts/git.md", "concepts/hg.md"]
    typed: list[tuple[dict[str, Any], list[str]]] = [
        ({"points": 3}, ["tasks/one.md"]),
        ({"score": 3.0}, ["tasks/one.md", "tasks/two.md"]),
        ({"urgent": True}, ["tasks/one.md"]),
        ({"due": dt.date(2026, 10, 6)}, ["tasks/one.md", "tasks/two.md"]),
        ({"at": dt.datetime(2026, 10, 6, 9, 30)}, ["tasks/one.md"]),
        ({"affects": "concepts/a.md"}, ["tasks/one.md", "tasks/three.md"]),
        ({"affects": vault / "concepts" / "a.md"}, ["tasks/one.md", "tasks/three.md"]),
        ({"affects": f"kid:{K1}"}, ["tasks/one.md", "tasks/three.md"]),
        ({"title": None}, ["tasks/three.md"]),
        ({"status": "todo", "tags": "red"}, ["tasks/one.md"]),
    ]
    for where, expected in typed:
        assert _paths(knott.entities("task", where=where)) == expected, where
    # one key twice needs pairs
    pairs = [("tags", "red"), ("tags", "blue")]
    assert _paths(knott.entities("task", where=pairs)) == ["tasks/one.md"]
    one = knott.entities("task", where={"points": 3}, fields=["due", "at", "nope"])[0]
    assert one.properties == {
        "due": dt.date(2026, 10, 6),
        "at": dt.datetime(2026, 10, 6, 9, 30),
        "nope": None,
    }
    assert one.model_dump(mode="json")["properties"]["due"] == "2026-10-06"
    utc = EntityRecord(
        path="a.md",
        type="t",
        kid=None,
        properties={"at": [dt.datetime(2026, 10, 6, 9, 30, tzinfo=dt.UTC)]},
    )
    assert utc.model_dump(mode="json")["properties"] == {"at": ["2026-10-06T09:30:00+00:00"]}


@pytest.mark.parametrize(
    ("type_name", "where"),
    [
        (None, {"status": "todo"}),
        ("ghost", None),
        ("task", {"nope": 1}),
        ("task", {"points": "3"}),
        ("task", {"points": True}),
        ("task", {"score": "3"}),
        ("task", {"urgent": 1}),
        ("task", {"due": "2026-10-06"}),
        ("task", {"due": dt.datetime(2026, 10, 6, 9, 30)}),
        ("task", {"status": "drafted"}),
        ("task", {"about": 3}),
        ("task", {"about": "notes/plain.md"}),
        ("task", {"steps": "x"}),
    ],
)
def test_entities_api_errors(
    vault: Path, type_name: str | None, where: dict[str, Any] | None
) -> None:
    with pytest.raises(KnottError):
        Knott.open(vault).entities(type_name, where=where)


def test_show_api(vault: Path) -> None:
    detail = Knott.open(vault).show("tasks/one.md")
    assert isinstance(detail, EntityDetail)
    assert detail.body is None
    assert detail.entity.properties is not None
    assert list(detail.entity.properties)[:3] == ["title", "code", "status"]
    assert detail.entity.properties["due"] == dt.date(2026, 10, 6)
    assert Knott.open(vault).show("concepts/a.md", body=True).body == "Body of A.\n"
