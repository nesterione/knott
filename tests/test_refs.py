"""Reverse lookup: `Knott.refs()` and `knott refs PATH` (spec 0006)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import Knott, KnottError, PathNotFoundError, PathOutsideVaultError, Refs
from knott.cli import app

from .conftest import fixture_path

runner = CliRunner()

VAULT = "relation-refs"
KID = "6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b"

RELATION_TEXT = """\
concepts/relation.md  concept

discussed_in
  decisions/0003-source-side-relations.md  decision    affects[0]
  decisions/0004-kid-references.md         decision    affects[0]
  issues/relation-invalid-value.md         issue_code  about

related
  concepts/entity.md  concept  related[0]  ⇄
  concepts/link.md    concept  related[1]  →
  concepts/schema.md  concept  related[1]  ←

← cites
  guides/writing-schemas.md  guide  cites[0]

← guide.concepts[]
  guides/writing-schemas.md  guide  concepts[2]

← guide.see
  guides/writing-schemas.md  guide  see
"""


def _refs(path: str, vault: Path | None = None) -> Refs:
    return Knott.open(vault or fixture_path(VAULT)).refs(path)


def _brief(refs: Refs) -> list[tuple[str, str, str | None, list[tuple[str, str, str]]]]:
    return [
        (g.label, g.kind, g.relation, [(r.path, r.field, r.direction) for r in g.references])
        for g in refs.groups
    ]


def test_groups_labels_kinds_and_order() -> None:
    refs = _refs("concepts/relation.md")
    assert refs.entity.model_dump() == {
        "path": "concepts/relation.md",
        "type": "concept",
        "kid": KID,
    }
    assert _brief(refs) == [
        # A relation with an inverse: grouped under the inverse, from every property naming it.
        (
            "discussed_in",
            "inverse",
            "about",
            [
                ("decisions/0003-source-side-relations.md", "affects[0]", "in"),
                # A `kid:` reference counts like a path.
                ("decisions/0004-kid-references.md", "affects[0]", "in"),
                ("issues/relation-invalid-value.md", "about", "in"),
            ],
        ),
        # A symmetric relation merges the entity's own outgoing references.
        (
            "related",
            "symmetric",
            "related",
            [
                ("concepts/entity.md", "related[0]", "both"),
                ("concepts/link.md", "related[1]", "out"),
                ("concepts/schema.md", "related[1]", "in"),
            ],
        ),
        # A relation with no inverse that is not symmetric.
        ("← cites", "relation", "cites", [("guides/writing-schemas.md", "cites[0]", "in")]),
        # Properties that name no relation come last.
        (
            "← guide.concepts[]",
            "property",
            None,
            [("guides/writing-schemas.md", "concepts[2]", "in")],
        ),
        # An undefined relation (`relation-unknown`) is a plain reference; a wrong target
        # type still points at the entity, so it is listed.
        ("← guide.see", "property", None, [("guides/writing-schemas.md", "see", "in")]),
    ]


def test_ref_types_kids_and_lines() -> None:
    groups = {g.label: g for g in _refs("concepts/relation.md").groups}
    discussed = groups["discussed_in"].references
    assert [(r.type, r.line, r.kid) for r in discussed] == [
        ("decision", 4, None),
        ("decision", 5, None),
        ("issue_code", 3, None),
    ]
    related = {r.path: r for r in groups["related"].references}
    # `out`: the link is stored in the looked-up entity, so field and line are its own.
    assert (related["concepts/link.md"].field, related["concepts/link.md"].line) == (
        "related[1]",
        6,
    )
    # `both`: field and line are those of the linked entity's reference.
    assert (related["concepts/entity.md"].field, related["concepts/entity.md"].line) == (
        "related[0]",
        4,
    )


def test_inverse_group_of_a_superseded_decision() -> None:
    assert _brief(_refs("decisions/0003-source-side-relations.md")) == [
        (
            "superseded_by",
            "inverse",
            "supersedes",
            [("decisions/0004-kid-references.md", "supersedes", "in")],
        )
    ]


def test_symmetric_only_outgoing_and_only_incoming() -> None:
    # link.md stores nothing; relation.md links to it, so link.md sees it as `in`.
    assert _brief(_refs("concepts/link.md")) == [
        ("related", "symmetric", "related", [("concepts/relation.md", "related[1]", "in")])
    ]
    # schema.md links to entity.md and relation.md; neither links back: both `out`.
    schema = _refs("concepts/schema.md")
    assert _brief(schema)[1] == (
        "related",
        "symmetric",
        "related",
        [
            ("concepts/entity.md", "related[0]", "out"),
            ("concepts/relation.md", "related[1]", "out"),
        ],
    )


def test_self_reference_in_a_symmetric_relation_is_both(
    copy_fixture: Callable[[str], Path],
) -> None:
    root = copy_fixture(VAULT)
    (root / "concepts/lonely.md").write_text("---\ntype: concept\nrelated:\n  - lonely.md\n---\n")
    assert _brief(_refs("concepts/lonely.md", root)) == [
        ("related", "symmetric", "related", [("concepts/lonely.md", "related[0]", "both")])
    ]


def test_kid_lookup_matches_path_lookup() -> None:
    assert _refs(f"kid:{KID}") == _refs("concepts/relation.md")


def test_no_references() -> None:
    refs = _refs("concepts/lonely.md")
    assert refs.groups == []


@pytest.mark.parametrize(
    ("given", "error", "message"),
    [
        ("missing.md", PathNotFoundError, "path does not exist: missing.md"),
        (
            ".knott/concepts/concept.md",
            KnottError,
            "not a Knott entity: .knott/concepts/concept.md",
        ),
        ("notes/plain.md", KnottError, "not a Knott entity: notes/plain.md"),
        ("concepts", KnottError, "not a Knott entity: concepts"),
        ("kid:00000000-0000-4000-8000-000000000000", KnottError, "no entity has `kid`"),
        ("kid:not-a-uuid", KnottError, "must be a lowercase UUID"),
    ],
)
def test_api_errors(given: str, error: type[Exception], message: str) -> None:
    with pytest.raises(error) as raised:
        _refs(given)
    assert message in str(raised.value)


def test_api_path_outside_vault(tmp_path: Path) -> None:
    outside = tmp_path / "x.md"
    outside.write_text("---\ntype: concept\n---\n")
    with pytest.raises(PathOutsideVaultError):
        _refs(str(outside))


def test_api_ambiguous_kid(copy_fixture: Callable[[str], Path]) -> None:
    root = copy_fixture(VAULT)
    (root / "concepts/copy.md").write_text(f"---\ntype: concept\nkid: {KID}\n---\n")
    with pytest.raises(KnottError, match="claimed by 2 entities"):
        _refs(f"kid:{KID}", root)


def test_api_invalid_frontmatter(copy_fixture: Callable[[str], Path]) -> None:
    root = copy_fixture(VAULT)
    (root / "concepts/broken.md").write_text("---\ntype: [concept\n---\n")
    with pytest.raises(KnottError, match=r"cannot read the frontmatter of concepts/broken\.md"):
        _refs("concepts/broken.md", root)


def test_api_hidden_folder_is_not_an_entity(copy_fixture: Callable[[str], Path]) -> None:
    root = copy_fixture(VAULT)
    (root / ".drafts").mkdir()
    (root / ".drafts/x.md").write_text("---\ntype: concept\n---\n")
    with pytest.raises(KnottError, match=r"not a Knott entity: \.drafts/x\.md"):
        _refs(".drafts/x.md", root)


def test_non_string_type_is_shown_in_yaml_form(copy_fixture: Callable[[str], Path]) -> None:
    # Regression: a list `type` was shown as "[…]` (2 items)".
    root = copy_fixture(VAULT)
    (root / "concepts/odd.md").write_text("---\ntype: [concept, guide]\n---\n")
    (root / "concepts/num.md").write_text("---\ntype: 7\n---\n")
    assert _refs("concepts/odd.md", root).entity.type == "[concept, guide]"
    assert _refs("concepts/num.md", root).entity.type == "7"


def test_shared_inverse_symmetric_inverse_and_field_order(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    knott_dir = tmp_path / ".knott"
    (knott_dir / "concepts/n.md").write_text(
        "---\nname: n\nproperties:\n"
        "  b: {type: reference, target: n, relation: rb}\n"
        "  a: {type: list, items: {type: reference, target: n, relation: ra}}\n"
        "  s: {type: reference, target: n, relation: symi}\n---\n"
    )
    (knott_dir / "relations").mkdir()
    # `ra` and `rb` share an inverse (relation-inverse-conflict); `symi` is symmetric
    # with an inverse (relation-symmetric-mismatch). Both still group.
    (knott_dir / "relations/rb.md").write_text("---\nname: rb\ninverse: back\n---\n")
    (knott_dir / "relations/ra.md").write_text("---\nname: ra\ninverse: back\n---\n")
    (knott_dir / "relations/symi.md").write_text(
        "---\nname: symi\nsymmetric: true\ninverse: symback\n---\n"
    )
    (tmp_path / "t.md").write_text("---\ntype: n\n---\n")
    items = "".join("  - t.md\n" for _ in range(11))
    (tmp_path / "src.md").write_text(f"---\ntype: n\nb: t.md\na:\n{items}s: t.md\n---\n")
    groups = _brief(_refs("t.md", tmp_path))
    # Two groups labelled `back`, one per relation, by relation name.
    assert [(label, kind, rel) for label, kind, rel, _ in groups] == [
        ("back", "inverse", "ra"),
        ("back", "inverse", "rb"),
        ("symback", "inverse", "symi"),
    ]
    # List items in list order: a[10] after a[9], not after a[1].
    assert [field for _, field, _ in groups[0][3]] == [f"a[{i}]" for i in range(11)]
    assert groups[2][3] == [("src.md", "s", "in")]


# CLI


@pytest.fixture
def in_vault(monkeypatch: pytest.MonkeyPatch) -> Path:
    vault = fixture_path(VAULT)
    monkeypatch.chdir(vault)
    return vault


def test_cli_text_output(in_vault: Path) -> None:
    result = runner.invoke(app, ["refs", "concepts/relation.md"])
    assert result.exit_code == 0, result.output
    assert result.stdout == RELATION_TEXT
    # Schema issues (here `relation-unknown`) don't stop it and aren't printed.
    assert result.stderr == ""


def test_cli_path_relative_to_current_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path(VAULT) / "concepts")
    result = runner.invoke(app, ["refs", "relation.md"])
    assert result.exit_code == 0, result.output
    assert result.stdout == RELATION_TEXT


def test_cli_kid(in_vault: Path) -> None:
    result = runner.invoke(app, ["refs", f"kid:{KID}"])
    assert result.exit_code == 0, result.output
    assert result.stdout == RELATION_TEXT


def test_cli_no_references(in_vault: Path) -> None:
    result = runner.invoke(app, ["refs", "concepts/lonely.md"])
    assert result.exit_code == 0
    assert result.stdout == "concepts/lonely.md  concept\n\nno references\n"


def test_cli_json(in_vault: Path) -> None:
    result = runner.invoke(app, ["refs", "concepts/relation.md", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["entity"] == {"path": "concepts/relation.md", "type": "concept", "kid": KID}
    assert payload["groups"][0] == {
        "label": "discussed_in",
        "kind": "inverse",
        "relation": "about",
        "references": [
            {
                "path": "decisions/0003-source-side-relations.md",
                "type": "decision",
                "kid": None,
                "field": "affects[0]",
                "line": 4,
                "direction": "in",
            },
            {
                "path": "decisions/0004-kid-references.md",
                "type": "decision",
                "kid": None,
                "field": "affects[0]",
                "line": 5,
                "direction": "in",
            },
            {
                "path": "issues/relation-invalid-value.md",
                "type": "issue_code",
                "kid": None,
                "field": "about",
                "line": 3,
                "direction": "in",
            },
        ],
    }
    assert [(g["label"], g["kind"], g["relation"]) for g in payload["groups"]] == [
        ("discussed_in", "inverse", "about"),
        ("related", "symmetric", "related"),
        ("← cites", "relation", "cites"),
        ("← guide.concepts[]", "property", None),
        ("← guide.see", "property", None),
    ]
    related = payload["groups"][1]["references"]
    assert [r["direction"] for r in related] == ["both", "out", "in"]


def test_cli_json_no_references(in_vault: Path) -> None:
    result = runner.invoke(app, ["refs", "concepts/lonely.md", "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "entity": {"path": "concepts/lonely.md", "type": "concept", "kid": None},
        "groups": [],
    }


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ("missing.md", "error: path does not exist: missing.md"),
        (".knott/concepts/concept.md", "error: not a Knott entity: .knott/concepts/concept.md"),
        ("notes/plain.md", "error: not a Knott entity: notes/plain.md"),
        ("kid:00000000-0000-4000-8000-000000000000", "error: no entity has `kid`"),
    ],
)
def test_cli_usage_errors(in_vault: Path, given: str, message: str) -> None:
    result = runner.invoke(app, ["refs", given])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr.startswith(message)


def test_cli_ambiguous_kid(
    copy_fixture: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = copy_fixture(VAULT)
    (root / "concepts/copy.md").write_text(f"---\ntype: concept\nkid: {KID}\n---\n")
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["refs", f"kid:{KID}"])
    assert result.exit_code == 2
    assert "claimed by 2 entities" in result.stderr


def test_cli_no_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.md").write_text("---\ntype: x\n---\n")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["refs", "a.md"])
    assert result.exit_code == 2
    assert result.stderr.startswith("error: no Knott vault found")


def test_cli_legacy_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    vault = fixture_path("legacy-layout")
    monkeypatch.chdir(vault)
    entity = next(p for p in sorted(vault.rglob("*.md")) if ".knott" not in p.parts)
    result = runner.invoke(app, ["refs", str(entity.relative_to(vault))])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("✗ .knott/schemas\n")
    assert "run `knott migrate`" in result.stderr


def test_refs_does_not_validate(copy_fixture: Callable[[str], Path]) -> None:
    # An entity that fails validation is still listed, and still looked up.
    root = copy_fixture(VAULT)
    (root / "concepts/bad.md").write_text(
        "---\ntype: concept\nrelated:\n  - relation.md\nunknown_key: 1\n---\n"
    )
    groups = {g.label: g for g in _refs("concepts/relation.md", root).groups}
    assert "concepts/bad.md" in [r.path for r in groups["related"].references]
    assert _refs("concepts/bad.md", root).entity.type == "concept"
