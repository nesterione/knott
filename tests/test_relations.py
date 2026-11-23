from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from knott import Knott, ValidationResult
from knott.vault.links import LinkError, parse_reference, resolve_reference

from .conftest import fixture_path, triples, validate_fixture


def test_missing_target_and_exact_case() -> None:
    result = validate_fixture("missing-relation-target")
    assert triples(result) == [
        ("transcripts/episode-42.md", 4, "relation-target-not-found"),
        ("transcripts/plain-note-target.md", 4, "relation-target-not-entity"),
        ("transcripts/wrong-case.md", 4, "relation-target-not-found"),
    ]


def test_wrong_target_type_message() -> None:
    result = validate_fixture("wrong-relation-target-type")
    assert triples(result) == [("transcripts/foo.md", 4, "relation-target-type-mismatch")]
    assert result.issues[0].field == "derived_from"
    assert result.issues[0].message == (
        "relation `derived_from` expects target type `script`\n"
        "but `../scripts/foo.md` has type `feedback`"
    )


def test_outside_vault_and_invalid_values() -> None:
    result = validate_fixture("relation-outside-vault")
    assert triples(result) == [
        ("transcripts/escape.md", 4, "relation-target-outside-vault"),
        ("transcripts/invalid-forms.md", 5, "relation-invalid-value"),  # URL
        ("transcripts/invalid-forms.md", 6, "relation-invalid-value"),  # fragment
        ("transcripts/invalid-forms.md", 7, "relation-invalid-value"),  # absolute
        ("transcripts/invalid-forms.md", 8, "relation-invalid-value"),  # not .md
        ("transcripts/invalid-forms.md", 9, "relation-invalid-value"),  # quoted wikilink
        ("transcripts/not-a-string.md", 4, "relation-invalid-value"),
        ("transcripts/unquoted-wikilink.md", 4, "relation-invalid-value"),
    ]
    unquoted = result.issues[-1]
    assert "Quote the value" in unquoted.message


def test_markdown_link_forms() -> None:
    result = validate_fixture("relation-markdown-link")
    assert result.ok, result.issues
    assert result.stats.relations == 3


def test_relation_lists_count_each_reference() -> None:
    result = validate_fixture("relation-list")
    assert triples(result) == [
        ("compilations/empty.md", 4, "relation-missing"),
        ("compilations/partly-broken.md", 6, "relation-target-not-found"),
    ]
    # best-of.md: 3 references; partly-broken.md: 1 good reference.
    assert result.stats.relations == 4


def test_relation_missing_when_absent(copy_fixture: Callable[[str], Path]) -> None:
    vault = copy_fixture("relation-list")
    (vault / "compilations/empty.md").write_text("---\ntype: compilation\n---\n")
    result = Knott.open(vault).validate()
    assert ("compilations/empty.md", None, "relation-missing") in triples(result)


@pytest.mark.parametrize(
    ("reference", "destination"),
    [
        ("../scripts/a.md", "../scripts/a.md"),
        ("[Label](../scripts/a.md)", "../scripts/a.md"),
        ("[](a.md)", "a.md"),
        ("[A](<../my scripts/a b.md>)", "../my scripts/a b.md"),
        ("[A](../my%20scripts/a%20b.md)", "../my scripts/a b.md"),
        ("  a.md  ", "a.md"),
    ],
)
def test_parse_reference(reference: str, destination: str) -> None:
    assert parse_reference(reference) == destination


@pytest.mark.parametrize(
    "reference",
    [
        "https://example.com/a.md",
        "file:a.md",
        "a.md#heading",
        "/abs/a.md",
        "a.txt",
        "[[a]]",
        "[A](a b.md)",
        "[A]",
        "[A]()",
        "",
    ],
)
def test_parse_reference_rejects(reference: str) -> None:
    with pytest.raises(LinkError) as excinfo:
        parse_reference(reference)
    assert excinfo.value.code == "relation-invalid-value"


def test_resolve_reference_is_relative_to_source_file() -> None:
    root = fixture_path("valid-vault")
    resolved = resolve_reference(root, "transcripts/x.md", "../scripts/episode-42.md")
    assert resolved.target == "scripts/episode-42.md"
    with pytest.raises(LinkError) as excinfo:
        resolve_reference(root, "x.md", "../x.md")
    assert excinfo.value.code == "relation-target-outside-vault"


def test_symlink_out_of_vault_is_outside(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    Knott.init(vault)
    (vault / ".knott/concepts/t.md").write_text(
        "---\nname: t\nproperties:\n  ref: {type: list, items: {type: reference, target: t}}\n---\n"
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "b.md").write_text("---\ntype: t\n---\n")
    (vault / "linked").symlink_to(outside, target_is_directory=True)
    (vault / "inner").mkdir()
    (vault / "inner/c.md").write_text("---\ntype: t\n---\n")
    (vault / "alias").symlink_to(vault / "inner", target_is_directory=True)
    (vault / "a.md").write_text("---\ntype: t\nref:\n  - linked/b.md\n  - alias/c.md\n---\n")
    result = Knott.open(vault).validate()
    # A symlink that stays inside the vault is fine; one that leaves it is not.
    assert triples(result) == [("a.md", 4, "relation-target-outside-vault")]


# --- references at any depth (decision 0010) ---------------------------------


def _issues(result: ValidationResult) -> list[tuple[str, int | None, str | None, str]]:
    return [(i.path, i.line, i.field, i.code) for i in result.issues]


def test_nested_references_in_objects_lists_and_maps() -> None:
    result = validate_fixture("nested-references")
    assert _issues(result) == [
        ("episodes/broken.md", 6, "speakers[1].person", "relation-target-not-found"),
        ("episodes/broken.md", 7, "speakers[2].person", "relation-target-type-mismatch"),
        ("episodes/broken.md", 8, "speakers[3].person", "relation-missing"),
        ("episodes/broken.md", 9, "speakers[4].person", "relation-target-not-found"),
        ("episodes/broken.md", 11, "hosts.lead", "relation-target-type-mismatch"),
        ("episodes/broken.md", 12, "hosts.backup", "relation-target-not-found"),
        ("episodes/broken.md", 14, "production.team", "relation-target-type-mismatch"),
    ]
    messages = {i.field: i.message for i in result.issues}
    assert messages["speakers[2].person"] == (
        "relation `speakers[2].person` expects target type `person`\n"
        "but `../teams/core.md` has type `team`"
    )
    assert messages["speakers[4].person"] == (
        "relation `speakers[4].person`: no entity has `kid` 99999999-9999-4999-8999-999999999999"
    )
    # good.md: 3 speakers (path, kid:, Markdown link) + hosts.lead + production.team;
    # broken.md: speakers[0].
    assert result.stats.relations == 6


def test_nested_references_valid_entity_only() -> None:
    result = validate_fixture("nested-references", ["episodes/good.md"])
    assert result.ok, result.issues
    assert result.stats.relations == 5


def test_union_targets() -> None:
    result = validate_fixture("union-target")
    entity_issues = [t for t in _issues(result) if not t[0].startswith(".knott")]
    # on-episode.md and on-meeting.md pass: each allowed type is accepted, and
    # `mystery` (every target unknown) keeps its shape but skips the type check.
    assert entity_issues == [
        ("notes/on-script.md", 3, "about", "relation-target-type-mismatch"),
        ("notes/on-script.md", 6, "sources[1]", "relation-target-type-mismatch"),
    ]
    mismatch = next(i for i in result.issues if i.field == "about")
    assert mismatch.message == (
        "relation `about` expects target type `episode` or `meeting`\n"
        "but `../scripts/s1.md` has type `script`"
    )
    # The unknown `podcast` in `sources` is dropped from the message.
    item = next(i for i in result.issues if i.field == "sources[1]")
    assert "`podcast`" not in item.message
    assert result.stats.relations == 6


def test_reference_cardinality_and_emptiness() -> None:
    result = validate_fixture("reference-cardinality")
    assert _issues(result) == [
        ("notes/absent.md", 5, "required_source", "relation-missing"),
        ("notes/absent.md", 6, "required_sources", "relation-missing"),
        ("notes/empty-containers.md", 3, "source", "relation-invalid-value"),
        ("notes/empty-containers.md", 4, "sources", "relation-invalid-value"),
        ("notes/empty-containers.md", 5, "required_source", "relation-invalid-value"),
        ("notes/empty-containers.md", 8, "required_sources[1]", "relation-invalid-value"),
        ("notes/empty-containers.md", 9, "required_sources[2]", "relation-invalid-value"),
        ("notes/wrong-kind.md", 3, "source", "relation-invalid-value"),
        ("notes/wrong-kind.md", 5, "sources", "relation-invalid-value"),
    ]
    messages = {(i.path, i.field): i.message for i in result.issues}
    assert "declare `type: list`" in messages[("notes/wrong-kind.md", "source")]
    assert (
        "expects list of reference → script but got string"
        in (messages[("notes/wrong-kind.md", "sources")])
    )
    assert "empty list" in messages[("notes/empty-containers.md", "source")]
    assert "add at least one reference" in messages[("notes/absent.md", "required_sources")]
    # valid.md: 4; wrong-kind.md: 2; empty-containers.md: required_sources[0].
    assert result.stats.relations == 7


def test_unquoted_wikilink_on_single_reference_hints_quoting() -> None:
    result = validate_fixture("relation-outside-vault", ["transcripts/unquoted-wikilink.md"])
    [issue] = result.issues
    assert (issue.field, issue.code) == ("derived_from", "relation-invalid-value")
    assert "Quote the value" in issue.message


def test_required_list_of_references_absent_is_relation_missing(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/concepts/t.md").write_text(
        "---\nname: t\nproperties:\n  refs:\n    type: list\n    required: true\n"
        "    items: {type: reference, target: t}\n---\n"
    )
    (tmp_path / "a.md").write_text("---\ntype: t\n---\n")
    result = Knott.open(tmp_path).validate()
    assert [(i.field, i.code) for i in result.issues] == [("refs", "relation-missing")]


def test_map_of_references_given_a_string(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/concepts/t.md").write_text(
        "---\nname: t\nproperties:\n  refs:\n    type: map\n"
        "    values: {type: reference, target: t}\n---\n"
    )
    (tmp_path / "a.md").write_text("---\ntype: t\nrefs: a.md\nother: {}\n---\n")
    (tmp_path / "b.md").write_text("---\ntype: t\nrefs: {}\n---\n")  # empty map is absent
    result = Knott.open(tmp_path).validate()
    assert triples(result) == [("a.md", 3, "relation-invalid-value")]
