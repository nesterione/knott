"""Concept inheritance: `extends` and `abstract` (spec 0013)."""

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
from knott.schema.models import subtypes_of
from knott.view import render_ontology

runner = CliRunner()

K = "{}{}{}{}{}{}{}{}-1111-4111-8111-111111111111"

CONCEPT = """---
name: concept
description: A named idea.
abstract: true
properties:
  title: { type: string, required: true }
  related:
    type: list
    items: { type: reference, target: concept }
---
# <!-- title -->
"""

TOOL = """---
name: tool
description: A piece of software.
extends: concept
properties:
  homepage: { type: string }
  made_by:  { type: reference, target: organization }
---
"""

ORGANIZATION = "---\nname: organization\nextends: concept\n---\n"
PERSON = "---\nname: person\nextends: concept\n---\n"
NOTE_ABOUT = (
    "---\nname: note\nproperties:\n  about: {type: reference, target: [concept, cli]}\n---\n"
)


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path, **concepts: str) -> Path:
    """The concept / tool / organization / person family, with ``concepts`` added or replaced."""
    root = tmp_path / "vault"
    files = {
        "concept": CONCEPT,
        "tool": TOOL,
        "organization": ORGANIZATION,
        "person": PERSON,
        **concepts,
    }
    for name, text in files.items():
        if text:
            _write(root, f".knott/concepts/{name}.md", text)
    return root


def _plain(tmp_path: Path, **concepts: str) -> Path:
    root = tmp_path / "vault"
    for name, text in concepts.items():
        _write(root, f".knott/concepts/{name}.md", text)
    return root


def _entity(root: Path, rel: str, frontmatter: str) -> None:
    _write(root, rel, f"---\n{frontmatter}---\n")


def _issues(root: Path) -> list[Issue]:
    return Knott.open(root).validate().issues


def _codes(issues: list[Issue]) -> list[tuple[str, str]]:
    return sorted((i.path, i.code) for i in issues)


# --- loading -------------------------------------------------------------------


def test_child_inherits_properties_root_first(tmp_path: Path) -> None:
    root = _vault(
        tmp_path, cli="---\nname: cli\nextends: tool\nproperties:\n  shell: {type: string}\n---\n"
    )
    loaded = load_definitions(root)
    assert loaded.issues == []
    cli = loaded.schemas["cli"]
    assert cli.ancestors == ("tool", "concept")
    assert list(cli.properties) == ["title", "related", "homepage", "made_by", "shell"]
    assert list(cli.own_properties) == ["shell"]
    assert cli.declared_in == {
        "title": "concept",
        "related": "concept",
        "homepage": "tool",
        "made_by": "tool",
    }
    assert cli.properties["title"].required is True
    assert cli.is_a("concept") and cli.is_a("tool") and cli.is_a("cli")
    assert not loaded.schemas["tool"].is_a("cli")
    assert subtypes_of(loaded.schemas, "concept") == ["cli", "organization", "person", "tool"]
    assert subtypes_of(loaded.schemas, "cli") == []


def test_abstract_is_not_inherited(tmp_path: Path) -> None:
    schemas = load_definitions(_vault(tmp_path)).schemas
    assert schemas["concept"].abstract is True
    assert schemas["tool"].abstract is False
    assert schemas["tool"].description == "A piece of software."
    assert schemas["organization"].description is None


@pytest.mark.parametrize(
    ("frontmatter", "field", "fragment"),
    [
        ("extends: [concept]\n", "extends", "must be the name of one concept"),
        ("extends: 3\n", "extends", "must be the name of one concept"),
        ("abstract: maybe\n", "abstract", "must be true or false"),
        ("abstract: 1\n", "abstract", "must be true or false"),
        ("abstract: yes\n", "abstract", "must be true or false"),
    ],
)
def test_invalid_keys_are_reported_and_dropped(
    tmp_path: Path, frontmatter: str, field: str, fragment: str
) -> None:
    root = _plain(tmp_path, a=f"---\nname: a\n{frontmatter}---\n", concept=CONCEPT)
    loaded = load_definitions(root)
    assert [(i.code, i.field, i.line) for i in loaded.issues] == [
        ("schema-invalid-field", field, 3)
    ]
    assert fragment in loaded.issues[0].message
    assert loaded.schemas["a"].extends is None
    assert loaded.schemas["a"].abstract is False


def test_empty_keys_mean_no_parent_and_concrete(tmp_path: Path) -> None:
    loaded = load_definitions(_plain(tmp_path, a="---\nname: a\nextends:\nabstract:\n---\n"))
    assert loaded.issues == []
    assert loaded.schemas["a"].extends is None


def test_unknown_parent(tmp_path: Path) -> None:
    root = _vault(tmp_path, tool=TOOL.replace("extends: concept", "extends: concpt"))
    loaded = load_definitions(root)
    assert [(i.code, i.path, i.field, i.line) for i in loaded.issues] == [
        ("schema-unknown-parent", ".knott/concepts/tool.md", "extends", 4)
    ]
    message = loaded.issues[0].message
    assert "`extends` names type `concpt`, which no concept defines" in message
    assert "did you mean `concept`?" in message
    assert "known types: `concept`, `organization`, `person`, `tool`" in message
    # `tool` loads as a root type, so `target: concept` does not accept its entities.
    assert loaded.schemas["tool"].ancestors == ()
    assert list(loaded.schemas["tool"].properties) == ["homepage", "made_by"]
    _entity(root, "t.md", "type: tool\n")
    _entity(root, "o.md", 'type: organization\ntitle: O\nrelated:\n  - "[t](t.md)"\n')
    assert ("o.md", "relation-target-type-mismatch") in _codes(_issues(root))


def test_parent_that_did_not_load_counts_as_unknown(tmp_path: Path) -> None:
    root = _vault(tmp_path, concept="---\nname: Bad Name\n---\n")
    codes = [(i.code, i.path) for i in load_definitions(root).issues]
    assert ("schema-unknown-parent", ".knott/concepts/tool.md") in codes
    assert ("schema-unknown-parent", ".knott/concepts/person.md") in codes


def test_extends_cycle(tmp_path: Path) -> None:
    root = _plain(
        tmp_path,
        a="---\nname: a\nextends: b\nproperties:\n  x: {type: string}\n---\n",
        b="---\nname: b\nextends: a\n---\n",
        c="---\nname: c\nextends: a\n---\n",
        d="---\nname: d\nextends: d\n---\n",
    )
    loaded = load_definitions(root)
    assert [(i.code, i.path, i.field, i.line) for i in loaded.issues] == [
        ("schema-extends-cycle", ".knott/concepts/a.md", "extends", 3),
        ("schema-extends-cycle", ".knott/concepts/b.md", "extends", 3),
        ("schema-extends-cycle", ".knott/concepts/d.md", "extends", 3),
    ]
    assert "`a` → `b` → `a`" in loaded.issues[0].message
    assert "`b` → `a` → `b`" in loaded.issues[1].message
    assert "`d` → `d`" in loaded.issues[2].message
    assert loaded.schemas["a"].ancestors == ()
    assert loaded.schemas["b"].ancestors == ()
    # `c` keeps its chain up to the first concept in the cycle.
    assert loaded.schemas["c"].ancestors == ("a",)
    assert list(loaded.schemas["c"].properties) == ["x"]


def test_property_redefined(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        tool="---\nname: tool\nextends: concept\nproperties:\n"
        "  homepage: {type: string}\n  title: {type: integer}\n---\n",
        cli="---\nname: cli\nextends: tool\nproperties:\n  related: {type: string}\n---\n",
    )
    loaded = load_definitions(root)
    assert [(i.code, i.path, i.field, i.line) for i in loaded.issues] == [
        ("schema-property-redefined", ".knott/concepts/cli.md", "properties.related", 5),
        ("schema-property-redefined", ".knott/concepts/tool.md", "properties.title", 6),
    ]
    assert (
        "property `title` is already declared by `concept` (`.knott/concepts/concept.md`), "
        "which `tool` extends"
    ) in loaded.issues[1].message
    # The child's definition is dropped and the inherited one stands.
    tool = loaded.schemas["tool"]
    assert list(tool.properties) == ["title", "related", "homepage"]
    assert tool.properties["title"].required is True
    assert list(tool.own_properties) == ["homepage"]


def test_siblings_may_declare_the_same_property(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        person="---\nname: person\nextends: concept\nproperties:\n"
        "  homepage: {type: integer}\n---\n",
    )
    assert load_definitions(root).issues == []


def test_unknown_target_of_an_inherited_reference_is_reported_once(tmp_path: Path) -> None:
    root = _vault(tmp_path, organization="")
    issues = load_definitions(root).issues
    assert [(i.code, i.path) for i in issues] == [
        ("schema-unknown-target", ".knott/concepts/tool.md")
    ]


def test_template_path_filename_and_kid(tmp_path: Path) -> None:
    root = _plain(
        tmp_path,
        base="---\nname: base\nkid: required\npath: concepts\n"
        'filename:\n  pattern: "{slug}"\n  parts:\n    slug: {match: "[a-z]+"}\n---\n# Base\n',
        same="---\nname: same\nextends: base\n---\n   \n",
        own="---\nname: own\nextends: base\npath: tools\nfilename:\n  pattern: index\n---\n# Own\n",
        deep="---\nname: deep\nextends: same\n---\n",
        root="---\nname: root\n---\n",
    )
    loaded = load_definitions(root)
    assert loaded.issues == []
    s = loaded.schemas
    assert s["same"].template == s["base"].template == "# Base\n"
    assert (s["same"].template_from, s["deep"].template_from) == ("base", "base")
    assert s["own"].template == "# Own\n" and s["own"].template_from is None
    assert s["same"].entity_paths == ("concepts",) and s["same"].entity_paths_from == "base"
    assert s["own"].entity_paths == ("tools",) and s["own"].entity_paths_from is None
    assert s["deep"].filename is s["base"].filename and s["deep"].filename_from == "base"
    assert s["own"].filename is not None and s["own"].filename.pattern == "index"
    assert s["same"].kid_required and s["same"].kid_required_from == "base"
    assert s["base"].kid_required_from is None
    assert (s["root"].template, s["root"].kid_required, s["root"].entity_paths) == (None, False, ())

    kid = "kid: 11111111-1111-4111-8111-111111111111\n"
    _entity(root, "concepts/a.md", "type: same\n")
    _entity(root, "concepts/b.md", f"type: own\n{kid}")
    _entity(root, "tools/index.md", "type: own\nkid: 22222222-2222-4222-8222-222222222222\n")
    _entity(root, "tools/X1.md", "type: deep\nkid: 33333333-3333-4333-8333-333333333333\n")
    assert _codes(_issues(root)) == [
        ("concepts/a.md", "kid-missing"),
        ("concepts/b.md", "entity-invalid-name"),
        ("concepts/b.md", "entity-misplaced"),
        ("tools/X1.md", "entity-invalid-name"),
        ("tools/X1.md", "entity-misplaced"),
    ]


# --- entities ------------------------------------------------------------------


def test_references_accept_subtypes(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        cli="---\nname: cli\nextends: tool\n---\n",
        note="---\nname: note\nproperties:\n  about: {type: reference, target: tool}\n"
        "  any: {type: reference, target: [organization, cli]}\n---\n",
    )
    _entity(root, "t.md", 'type: tool\ntitle: T\nrelated:\n  - "[o](o.md)"\n  - "[c](c.md)"\n')
    _entity(root, "o.md", "type: organization\ntitle: O\n")
    _entity(root, "c.md", "type: cli\ntitle: C\n")
    _entity(root, "ok1.md", 'type: note\nabout: "[t](t.md)"\nany: "[c](c.md)"\n')
    _entity(root, "ok2.md", 'type: note\nabout: "[c](c.md)"\nany: "[o](o.md)"\n')
    _entity(root, "bad.md", 'type: note\nabout: "[o](o.md)"\nany: "[t](t.md)"\n')
    issues = _issues(root)
    assert [(i.path, i.field, i.code) for i in issues] == [
        ("bad.md", "about", "relation-target-type-mismatch"),
        ("bad.md", "any", "relation-target-type-mismatch"),
    ]
    # The message names the declared targets, as before.
    assert "expects target type `tool`\n" in issues[0].message
    assert "expects target type `organization` or `cli`\n" in issues[1].message


def test_narrow_target_rejects_the_parent_type(tmp_path: Path) -> None:
    root = _vault(tmp_path, concept=CONCEPT.replace("abstract: true\n", ""))
    _entity(root, "c.md", "type: concept\ntitle: C\n")
    _entity(root, "t.md", 'type: tool\ntitle: T\nmade_by: "[c](c.md)"\n')
    assert _codes(_issues(root)) == [("t.md", "relation-target-type-mismatch")]


def test_entity_of_an_abstract_type(tmp_path: Path) -> None:
    root = _vault(tmp_path, cli="---\nname: cli\nextends: tool\nabstract: true\n---\n")
    _entity(root, "c.md", "type: concept\n")
    _entity(root, "t.md", 'type: tool\ntitle: T\nrelated:\n  - "[c](c.md)"\n')
    issues = _issues(root)
    assert [(i.path, i.line, i.field, i.code) for i in issues] == [
        ("c.md", None, "title", "attribute-missing"),
        ("c.md", 2, "type", "entity-abstract-type"),
    ]
    # Concrete subtypes at any depth, sorted; the abstract `cli` is left out.
    assert issues[1].message == (
        "`concept` is abstract and cannot be an entity's type; "
        "use `organization`, `person` or `tool`"
    )


def test_abstract_type_messages_by_number_of_subtypes(tmp_path: Path) -> None:
    root = _plain(
        tmp_path,
        lone="---\nname: lone\nabstract: true\n---\n",
        one="---\nname: one\nabstract: true\n---\n",
        child="---\nname: child\nextends: one\n---\n",
    )
    _entity(root, "a.md", "type: lone\n")
    _entity(root, "b.md", "type: one\n")
    messages = [i.message for i in _issues(root)]
    assert messages == [
        "`lone` is abstract and cannot be an entity's type",
        "`one` is abstract and cannot be an entity's type; use `child`",
    ]


def test_issue_on_an_inherited_property_names_the_declaring_file(tmp_path: Path) -> None:
    root = _vault(tmp_path, cli="---\nname: cli\nextends: tool\n---\n")
    _entity(root, "t.md", "type: tool\nhomepage: 4\n")
    _entity(root, "c.md", "type: cli\nhomepage: 4\n")
    by_key = {(i.path, i.field): i.message for i in _issues(root)}
    assert by_key[("t.md", "title")] == (
        "required attribute `title` (string) is missing or empty\n"
        "declared in .knott/concepts/concept.md (`tool` extends `concept`)"
    )
    assert "declared in" not in by_key[("t.md", "homepage")]
    assert by_key[("c.md", "title")].endswith(
        "declared in .knott/concepts/concept.md (`cli` extends `concept` through `tool`)"
    )
    assert by_key[("c.md", "homepage")].endswith(
        "declared in .knott/concepts/tool.md (`cli` extends `tool`)"
    )


def test_refs_and_cycles_go_through_subtypes(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        concept=CONCEPT.replace(
            "items: { type: reference, target: concept }",
            "items: { type: reference, relation: builds-on, target: concept }",
        ),
    )
    _write(root, ".knott/relations/builds-on.md", "---\nname: builds-on\nacyclic: true\n---\n")
    _entity(root, "t.md", 'type: tool\ntitle: T\nrelated:\n  - "[o](o.md)"\n')
    _entity(root, "o.md", 'type: organization\ntitle: O\nrelated:\n  - "[p](p.md)"\n')
    _entity(root, "p.md", 'type: person\ntitle: P\nrelated:\n  - "[t](t.md)"\n')
    assert [i.code for i in _issues(root)] == ["relation-cycle"]
    refs = Knott.open(root).refs("o.md")
    assert [(r.path, r.type) for g in refs.groups for r in g.references] == [("t.md", "tool")]


# --- relation definitions ------------------------------------------------------


def _relation_vault(tmp_path: Path, concept_target: str, tool_extra: str = "") -> Path:
    root = _vault(
        tmp_path,
        concept="---\nname: concept\nproperties:\n  title: {type: string}\n"
        + concept_target
        + "---\n",
        tool="---\nname: tool\nextends: concept\nproperties:\n  homepage: {type: string}\n"
        + tool_extra
        + "---\n",
    )
    return root


def test_symmetric_relation_on_a_child_targeting_the_parent(tmp_path: Path) -> None:
    root = _relation_vault(
        tmp_path, "", "  related: {type: reference, relation: related, target: concept}\n"
    )
    _write(root, ".knott/relations/related.md", "---\nname: related\nsymmetric: true\n---\n")
    assert load_definitions(root).issues == []


def test_symmetric_relation_on_a_parent_targeting_the_child(tmp_path: Path) -> None:
    root = _relation_vault(
        tmp_path, "  related: {type: reference, relation: related, target: tool}\n"
    )
    _write(root, ".knott/relations/related.md", "---\nname: related\nsymmetric: true\n---\n")
    issues = load_definitions(root).issues
    # Once, at the concept that declares the property, not once per child.
    assert [(i.code, i.path) for i in issues] == [
        ("relation-symmetric-mismatch", ".knott/concepts/concept.md")
    ]


def test_inverse_conflict_with_an_inherited_property(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        note="---\nname: note\nproperties:\n"
        "  about: {type: reference, relation: about, target: tool}\n"
        "  cites: {type: reference, relation: cites, target: concept}\n---\n",
    )
    _write(root, ".knott/relations/about.md", "---\nname: about\ninverse: title\n---\n")
    _write(root, ".knott/relations/cites.md", "---\nname: cites\ninverse: homepage\n---\n")
    issues = load_definitions(root).issues
    assert [(i.code, i.path) for i in issues] == [
        ("relation-inverse-conflict", ".knott/relations/about.md"),
        ("relation-inverse-conflict", ".knott/relations/cites.md"),
    ]
    # `title` is inherited by `tool`: reported once, at `concept`, which declares it.
    assert "property of concept `concept`" in issues[0].message
    assert "inherited by a concept this relation can point at" in issues[0].message
    assert "which this relation can point at" in issues[1].message
    # `homepage` belongs to `tool`, a subtype of the target `concept`.
    assert "property of concept `tool`" in issues[1].message


# --- loops ---------------------------------------------------------------------

STATUS = "  status: {type: enum, options: [draft, done]}\n"


def _loop_vault(tmp_path: Path) -> Path:
    root = _vault(
        tmp_path,
        concept="---\nname: concept\nabstract: true\nproperties:\n"
        "  title: {type: string}\n" + STATUS + "  summary: {type: string}\n---\n",
        note="---\nname: note\nproperties:\n"
        "  about: {type: reference, relation: about, target: concept}\n---\n",
        memo="---\nname: memo\nextends: note\n---\n",
    )
    _write(root, ".knott/relations/about.md", "---\nname: about\ninverse: notes\n---\n")
    _write(
        root,
        ".knott/loops/flow.md",
        "---\nname: flow\ntype: concept\nproperty: status\nstages:\n  draft:\n"
        "  done: {needs: [summary, notes: note]}\n---\n",
    )
    return root


def test_loop_follows_subtypes_and_inherited_properties(tmp_path: Path) -> None:
    root = _loop_vault(tmp_path)
    assert load_definitions(root).issues == []
    _entity(root, "t.md", "type: tool\ntitle: T\nstatus: done\nsummary: s\n")
    _entity(root, "o.md", "type: organization\nstatus: draft\n")
    _entity(root, "p.md", "type: person\nstatus: done\n")
    # A `memo` is a `note`, so it meets the need `notes: note`.
    _entity(root, "m.md", 'type: memo\nabout: "[t](t.md)"\n')
    report = Knott.open(root).loops("flow")
    placed = {s.stage: [(e.path, e.type) for e in s.entities] for s in report.stages}
    assert placed == {
        "draft": [("o.md", "organization")],
        "done": [("p.md", "person"), ("t.md", "tool")],
    }
    done = {e.path: e for e in report.stages[1].entities}
    assert done["t.md"].unmet == []
    assert [n.property or n.inverse for n in done["p.md"].unmet] == ["summary", "notes"]
    assert _codes(_issues(root)) == [("p.md", "loop-stage-unmet"), ("p.md", "loop-stage-unmet")]


def test_loops_json_has_the_entity_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _loop_vault(tmp_path)
    _entity(root, "t.md", "type: tool\nstatus: draft\n")
    monkeypatch.chdir(root)
    data = json.loads(runner.invoke(app, ["loops", "flow", "--format", "json"]).output)
    assert '"type": "tool"' in json.dumps(data)
    text = runner.invoke(app, ["loops", "flow"]).output
    assert "t.md" in text and "tool" not in text


def test_loops_on_a_type_and_its_subtype_are_duplicates(tmp_path: Path) -> None:
    root = _loop_vault(tmp_path)
    _write(
        root,
        ".knott/loops/tools.md",
        "---\nname: tools\ntype: tool\nproperty: status\nstages:\n  draft:\n---\n",
    )
    issues = load_definitions(root).issues
    assert [(i.code, i.path) for i in issues] == [
        ("schema-duplicate-loop", ".knott/loops/tools.md")
    ]
    assert "on `concept` and on `tool`, and one of them extends the other" in issues[0].message


def test_loops_on_siblings_are_not_duplicates(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        tool="---\nname: tool\nextends: concept\nproperties:\n" + STATUS + "---\n",
        person="---\nname: person\nextends: concept\nproperties:\n" + STATUS + "---\n",
    )
    for name in ("tool", "person"):
        _write(
            root,
            f".knott/loops/{name}.md",
            f"---\nname: {name}\ntype: {name}\nproperty: status\nstages:\n  draft:\n---\n",
        )
    assert load_definitions(root).issues == []


# --- CLI and API ---------------------------------------------------------------


def test_ontology(tmp_path: Path) -> None:
    root = _vault(tmp_path, cli="---\nname: cli\nextends: tool\n---\n")
    _entity(root, "t.md", "type: tool\ntitle: T\n")
    by_type = {t.type: t for t in Knott.open(root).ontology().types}
    concept, tool, cli = by_type["concept"], by_type["tool"], by_type["cli"]
    assert (concept.extends, concept.abstract, concept.ancestors) == (None, True, [])
    assert concept.subtypes == ["organization", "person", "tool"]
    assert (tool.extends, tool.abstract, tool.subtypes) == ("concept", False, ["cli"])
    assert cli.ancestors == ["tool", "concept"]
    assert [(a.name, a.inherited_from) for a in cli.properties] == [
        ("title", "concept"),
        ("related", "concept"),
        ("homepage", "tool"),
        ("made_by", "tool"),
    ]
    assert [a.inherited_from for a in concept.properties] == [None, None]
    assert cli.template == concept.template == "# <!-- title -->\n"
    assert cli.inherited == {"template": "concept"}
    assert concept.inherited == {}
    assert (concept.count, tool.count, cli.count) == (0, 1, 0)
    assert [path for path, _ in cli.references()] == ["related[]", "made_by"]


def test_types_verbose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(
        tmp_path,
        concept=CONCEPT.replace(
            "abstract: true\n", "abstract: true\nkid: required\npath: concepts/**\n"
        ),
    )
    monkeypatch.chdir(root)
    plain = runner.invoke(app, ["types"]).output
    assert plain == "concept\norganization\nperson\ntool\n"
    out = runner.invoke(app, ["types", "--verbose"]).output
    assert (
        "concept  (.knott/concepts/concept.md)\n"
        "  A named idea.\n"
        "  abstract: yes\n"
        "  subtypes: organization, person, tool\n"
        "  kid: required\n"
        "  template: yes\n"
        "  path: concepts/**\n"
        "  references: related[]\n"
        "  properties:\n"
        "    title*   string\n"
        "    related  list of reference → concept\n"
    ) in out
    assert (
        "tool  (.knott/concepts/tool.md)\n"
        "  A piece of software.\n"
        "  extends: concept\n"
        "  kid: required (from concept)\n"
        "  template: yes (from concept)\n"
        "  path: concepts/** (from concept)\n"
        "  references: related[], made_by\n"
        "  properties (from concept):\n"
        "    title*   string\n"
        "    related  list of reference → concept\n"
        "  properties:\n"
        "    homepage  string\n"
        "    made_by   reference → organization\n"
    ) in out
    # A child with no properties of its own has no bare `properties:` block.
    person = out.split("person  (")[1].split("\n\n")[0]
    assert "  properties (from concept):\n" in person
    assert "  properties:\n" not in person


def test_vault_without_the_keys_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _plain(tmp_path, a="---\nname: a\nproperties:\n  x: {type: string}\n---\n")
    monkeypatch.chdir(root)
    out = runner.invoke(app, ["types", "--verbose"]).output
    assert out.startswith(
        "a  (.knott/concepts/a.md)\n  template: no\n  references: none\n"
        "  properties:\n    x  string\n"
    )


# --- view ----------------------------------------------------------------------


def _view_data(root: Path) -> dict[str, Any]:
    vault = Knott.open(root)
    html = render_ontology(vault.ontology(), vault.loops())
    start = html.index("const DATA = ") + len("const DATA = ")
    data: dict[str, Any] = json.JSONDecoder().raw_decode(html, start)[0]
    return data


def test_view_draws_a_reference_once_at_the_declaring_type(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        cli="---\nname: cli\nextends: tool\n---\n",
        note=NOTE_ABOUT,
    )
    _entity(root, "t.md", "type: tool\ntitle: T\n")
    _entity(root, "c.md", "type: cli\ntitle: C\n")
    data = _view_data(root)
    assert [(e["source"], e["target"], e["path"]) for e in data["edges"]] == [
        ("concept", "concept", "related[]"),
        ("note", "concept", "about"),
        ("note", "cli", "about"),
        ("tool", "organization", "made_by"),
    ]
    assert data["inheritance"] == [
        {"child": "cli", "parent": "tool"},
        {"child": "organization", "parent": "concept"},
        {"child": "person", "parent": "concept"},
        {"child": "tool", "parent": "concept"},
    ]
    assert [(p["type"], p["path"]) for p in data["reference_properties"]] == [
        ("concept", "related[]"),
        ("note", "about"),
        ("tool", "made_by"),
    ]
    types = {t["type"]: t for t in data["types"]}
    assert types["concept"]["count_with_subtypes"] == 2
    assert types["tool"]["count_with_subtypes"] == 2
    assert types["cli"]["count_with_subtypes"] == 1
    assert (types["concept"]["abstract"], types["tool"]["extends"]) == (True, "concept")
    assert types["cli"]["ancestors"] == ["tool", "concept"]
    assert types["concept"]["subtypes"] == ["organization", "person", "tool"]
    assert [a["inherited_from"] for a in types["tool"]["properties"]] == [
        "concept",
        "concept",
        None,
        None,
    ]


def test_view_referenced_by_reaches_subtypes_through_an_ancestor(tmp_path: Path) -> None:
    root = _vault(
        tmp_path,
        cli="---\nname: cli\nextends: tool\n---\n",
        note=NOTE_ABOUT,
    )
    rows = {
        r["type"]: sorted(
            (ref["type"], ref["path"], ref["via"]) for g in r["groups"] for ref in g["references"]
        )
        for r in _view_data(root)["referenced_by"]
    }
    assert rows["concept"] == [("concept", "related[]", None), ("note", "about", None)]
    assert rows["tool"] == [("concept", "related[]", "concept"), ("note", "about", "concept")]
    # `cli` is a declared target of `note.about`: no `via`, though `concept` reaches it too.
    assert rows["cli"] == [("concept", "related[]", "concept"), ("note", "about", None)]
    assert rows["organization"] == [
        ("concept", "related[]", "concept"),
        ("note", "about", "concept"),
        ("tool", "made_by", None),
    ]


def test_view_loop_cards_carry_the_entity_type(tmp_path: Path) -> None:
    root = _loop_vault(tmp_path)
    _entity(root, "t.md", "type: tool\nstatus: draft\n")
    report = _view_data(root)["loop_reports"][0]
    assert report["stages"][0]["entities"][0]["type"] == "tool"


def test_view_template_reads_the_inheritance_data() -> None:
    template = view._template()
    for needle in (
        "DATA.inheritance",
        "t.count_with_subtypes",
        "t.extends",
        "t.abstract",
        "t.ancestors",
        "t.subtypes",
        "a.inherited_from",
        "r.via",
        "e.type",
        "Fold subtypes",
        "Unfold subtypes",
    ):
        assert needle in template, needle
