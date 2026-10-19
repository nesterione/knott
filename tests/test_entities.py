from __future__ import annotations

from pathlib import Path

import pytest

from knott import Knott
from knott.vault.entity import parse_markdown

from .conftest import triples, validate_fixture


def test_valid_vault_ignores_plain_notes_and_dot_directories() -> None:
    result = validate_fixture("valid-vault")
    assert result.ok, result.issues
    # Plain notes, untyped notes, and .obsidian/ files are not entities.
    assert result.stats.model_dump() == {"schemas": 3, "entities": 3, "relations": 2}


def test_unknown_type() -> None:
    result = validate_fixture("unknown-type")
    assert triples(result) == [("notes/mystery.md", 2, "entity-unknown-type")]
    assert result.issues[0].field == "type"
    assert "`podcast`" in result.issues[0].message


def test_missing_required_attribute() -> None:
    result = validate_fixture("missing-required-field")
    assert triples(result) == [
        ("scripts/blank-title.md", 3, "attribute-missing"),  # present but empty
        ("scripts/untitled.md", None, "attribute-missing"),  # absent: line unknown
    ]


def test_invalid_frontmatter_is_reported_not_skipped() -> None:
    result = validate_fixture("invalid-frontmatter")
    assert triples(result) == [
        ("broken-yaml.md", 3, "entity-invalid-frontmatter"),
        ("not-a-mapping.md", 1, "entity-invalid-frontmatter"),
        ("unclosed.md", 1, "entity-invalid-frontmatter"),
        ("unquoted-link.md", 4, "entity-invalid-frontmatter"),
    ]
    # BOM + CRLF file parses fine and counts as an entity.
    assert result.stats.entities == 2


def test_unquoted_markdown_link_suggests_quoting() -> None:
    result = validate_fixture("invalid-frontmatter")
    issue = next(i for i in result.issues if i.path == "unquoted-link.md")
    assert "quoted" in issue.message


def test_undeclared_keys_are_not_checked(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/t.yaml").write_text("type: t\n")
    (tmp_path / "a.md").write_text("---\ntype: t\nlink: ../nowhere.md\nn: 1\n---\n")
    assert Knott.open(tmp_path).validate().ok


def test_non_string_type_is_unknown(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / "a.md").write_text("---\ntype: 3\n---\n")
    (tmp_path / "b.md").write_text("---\ntype:\n---\n")
    result = Knott.open(tmp_path).validate()
    assert triples(result) == [
        ("a.md", 2, "entity-unknown-type"),
        ("b.md", 2, "entity-unknown-type"),
    ]


def test_symlinked_directories_are_not_followed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    Knott.init(vault)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.md").write_text("---\ntype: missing\n---\n")
    (vault / "linked").symlink_to(outside, target_is_directory=True)
    result = Knott.open(vault).validate()
    assert result.ok
    assert result.stats.entities == 0


def test_yaml_alias_bomb_is_rejected(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    lines = ["---", "type: x", "a0: &a0 [x, x, x, x, x, x, x, x, x]"]
    for i in range(1, 9):
        lines.append(f"a{i}: &a{i} [" + ", ".join([f"*a{i - 1}"] * 9) + "]")
    lines.append("---")
    (tmp_path / "bomb.md").write_text("\n".join(lines) + "\n")
    result = Knott.open(tmp_path).validate()
    assert [i.code for i in result.issues] == ["entity-invalid-frontmatter"]
    assert "too many" in result.issues[0].message


def test_deeply_nested_yaml_is_reported_not_raised(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / "deep.md").write_text("---\ntype: x\nv: " + "[" * 5000 + "]" * 5000 + "\n---\n")
    result = Knott.open(tmp_path).validate()
    assert triples(result) == [("deep.md", None, "entity-invalid-frontmatter")]


def test_invalid_characters_are_reported_not_raised(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / "nul.md").write_bytes(b"---\ntype: t\nextra: \x00\n---\n")
    result = Knott.open(tmp_path).validate()
    assert triples(result) == [("nul.md", 3, "entity-invalid-frontmatter")]


def test_non_string_keys_do_not_satisfy_fields(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/t.yaml").write_text(
        "type: t\nattributes:\n  'True':\n    type: string\n    required: true\n"
    )
    (tmp_path / "a.md").write_text("---\ntype: t\nyes: works\n---\n")
    result = Knott.open(tmp_path).validate()
    assert triples(result) == [("a.md", None, "attribute-missing")]


def test_merge_key_alias_bomb_is_rejected(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    body = "type: t\na0: &a0 {x: 0}\n"
    body += "".join(f"a{i}: &a{i} {{<<: [*a{i - 1}, *a{i - 1}]}}\n" for i in range(1, 26))
    (tmp_path / "merge.md").write_text("---\n" + body + "---\n")
    result = Knott.open(tmp_path).validate()
    assert [i.code for i in result.issues] == ["entity-invalid-frontmatter"]
    assert "too many" in result.issues[0].message


def test_shared_alias_value_in_message_stays_small(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/t.yaml").write_text(
        "type: t\nattributes:\n  flag:\n    type: boolean\n"
    )
    body = "type: t\na0: &a0 [x]\n"
    body += "".join(f"a{i}: &a{i} [*a{i - 1}, *a{i - 1}]\n" for i in range(1, 12))
    body += "flag: *a11\n"
    (tmp_path / "a.md").write_text("---\n" + body + "---\n")
    result = Knott.open(tmp_path).validate()
    assert [i.code for i in result.issues] == ["attribute-type-mismatch"]
    assert len(result.issues[0].message) < 200


def test_quoted_and_boolean_keys_are_distinct(tmp_path: Path) -> None:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/t.yaml").write_text(
        'type: t\nattributes:\n  "true":\n    type: boolean\n'
    )
    (tmp_path / "a.md").write_text('---\ntype: t\n"true": yes\ntrue: true\n---\n')
    (tmp_path / "b.md").write_text('---\ntype: t\n"true": false\ntrue: yes\n---\n')
    result = Knott.open(tmp_path).validate()
    assert triples(result) == [("a.md", 3, "attribute-type-mismatch")]


@pytest.mark.parametrize("value", ["!!bool nope", "!!timestamp nope", '!!int ""', '!!float ""'])
def test_bad_explicit_tags_are_reported_not_raised(tmp_path: Path, value: str) -> None:
    Knott.init(tmp_path)
    (tmp_path / "a.md").write_text(f"---\ntype: t\nx: {value}\n---\n")
    result = Knott.open(tmp_path).validate()
    assert [i.code for i in result.issues] == ["entity-invalid-frontmatter"]


def test_nested_values_keep_their_lines_and_source_text() -> None:
    text = (
        "---\n"
        "type: lexeme\n"
        "senses:\n"
        "  - {id: friend, ru: друг}\n"
        "  - id: home\n"
        "    ru: 5\n"
        "forms:\n"
        "  sg: {nom: draũgas, gen: draũgo}\n"
        "base: &b {done: yes}\n"
        "copy: *b\n"
        "---\n"
    )
    parsed = parse_markdown(text, "a.md")
    assert parsed.lines[("senses", 0)] == 4
    assert parsed.lines[("senses", 0, "ru")] == 4
    assert parsed.lines[("senses", 1, "ru")] == 6
    assert parsed.raws[("senses", 1, "ru")] == "5"
    assert parsed.lines[("forms", "sg", "gen")] == 8
    assert parsed.raws[("forms", "sg", "gen")] == "draũgo"
    # Aliased values get metadata under every path that reaches them.
    assert parsed.raws[("copy", "done")] == "yes"
    # Missing nested keys fall back to the nearest ancestor's line.
    assert parsed.line_of(("senses", 1, "missing")) == 5
    assert parsed.line_of(("absent", "x")) is None
    # Top-level maps are unchanged.
    assert parsed.key_lines["forms"] == 7
    assert parsed.item_lines[("senses", 1)] == 5
