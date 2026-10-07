from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from knott import Knott
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
    (vault / ".knott/schemas/t.yaml").write_text("type: t\nrelations:\n  ref:\n    target: t\n")
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
