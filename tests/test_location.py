"""Entity location: the concept's `path` key (spec 0011)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import Knott
from knott.cli import app
from knott.models import Issue
from knott.schema.loader import load_definitions
from knott.schema.paths import entity_folder, folder_matches, normalize_pattern, pattern_problem
from knott.view import render_ontology

runner = CliRunner()


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _vault(tmp_path: Path, path_yaml: str | None, name: str = "episode") -> Path:
    root = tmp_path / "vault"
    extra = "" if path_yaml is None else f"path: {path_yaml}\n"
    _write(root, f".knott/concepts/{name}.md", f"---\nname: {name}\n{extra}---\n")
    return root


def _entity(root: Path, rel: str, type_name: str = "episode") -> None:
    _write(root, rel, f"---\ntitle: x\ntype: {type_name}\n---\n")


def _misplaced(root: Path) -> list[Issue]:
    return [i for i in Knott.open(root).validate().issues if i.code == "entity-misplaced"]


@pytest.mark.parametrize(
    ("pattern", "folder", "expected"),
    [
        ("specs", "specs", True),
        ("specs", "specs/old", False),
        ("specs", "Specs", False),
        ("specs", ".", False),
        (".", ".", True),
        (".", "specs", False),
        ("episodes/*", "episodes/2026", True),
        ("episodes/*", "episodes", False),
        ("episodes/*", "episodes/2026/q1", False),
        ("episodes/**", "episodes", True),
        ("episodes/**", "episodes/2026/q1", True),
        ("episodes/**", "episodes-old", False),
        ("**/specs", "specs", True),
        ("**/specs", "a/b/specs", True),
        ("**/specs", "a/specs/b", False),
        ("**", ".", True),
        ("**", "a/b", True),
        ("a/**/z", "a/z", True),
        ("a/**/z", "a/b/c/z", True),
        ("drafts-*", "drafts-", True),
        ("drafts-*", "drafts-2026", True),
        ("drafts-*", "drafts", False),
        ("*-a-*", "x-a-y", True),
        ("*-a-*", "-a-", True),
        ("*-a-*", "x-b-y", False),
        ("a*a", "a", False),
        ("a*a", "aa", True),
        ("a?c", "abc", False),
        ("a?c", "a?c", True),
        ("[ab]", "a", False),
    ],
)
def test_folder_matches(pattern: str, folder: str, expected: bool) -> None:
    assert pattern_problem(pattern) is None
    assert folder_matches(pattern, folder) is expected


def test_entity_folder() -> None:
    assert entity_folder("a.md") == "."
    assert entity_folder("specs/old/a.md") == "specs/old"


def test_trailing_slash_is_ignored() -> None:
    assert normalize_pattern("specs/") == "specs"
    assert normalize_pattern("specs//") == "specs/"
    assert normalize_pattern("/") == "/"


@pytest.mark.parametrize(
    ("path_yaml", "line", "fragment"),
    [
        ("3", 3, "must be a folder pattern or a non-empty list"),
        ("[]", 3, "must be a folder pattern or a non-empty list"),
        ("{a: b}", 3, "must be a folder pattern or a non-empty list"),
        ('""', 3, "is empty"),
        ("/specs", 3, "starts with `/`"),
        ("/", 3, "starts with `/`"),
        ("'a\\b'", 3, "contains `\\`"),
        ("a//b", 3, "empty segment"),
        ("specs//", 3, "empty segment"),
        ("./specs", 3, "`.` segment"),
        ("specs/../x", 3, "`..` segment"),
        ("a**", 3, "must be a whole segment"),
        ("\n  - specs\n  - 4", 5, "must be a string"),
        ("\n  - specs\n  - notes\n  - specs/", 6, "listed twice"),
    ],
)
def test_invalid_path_is_reported_and_dropped(
    tmp_path: Path, path_yaml: str, line: int, fragment: str
) -> None:
    root = _vault(tmp_path, path_yaml)
    loaded = load_definitions(root)
    assert [(i.code, i.field, i.line) for i in loaded.issues] == [
        ("schema-invalid-field", "path", line)
    ]
    assert fragment in loaded.issues[0].message
    # The concept still loads, without `path`.
    assert loaded.schemas["episode"].entity_paths == ()
    _entity(root, "anywhere/a.md")
    assert _misplaced(root) == []


def test_many_double_stars_on_a_deep_folder_do_not_hang() -> None:
    pattern = "/".join(["**"] * 30) + "/x"
    assert folder_matches(pattern, "/".join(["a"] * 60)) is False
    assert folder_matches(pattern, "/".join(["a"] * 60) + "/x") is True


def test_pattern_starting_with_a_star_is_quoted(tmp_path: Path) -> None:
    root = _vault(tmp_path, '"**/specs"')
    loaded = load_definitions(root)
    assert loaded.issues == []
    assert loaded.schemas["episode"].entity_paths == ("**/specs",)
    _entity(root, "a/b/specs/x.md")
    _entity(root, "a/b/x.md")
    assert [i.path for i in _misplaced(root)] == ["a/b/x.md"]
    # Unquoted, YAML reads the leading `*` as an alias.
    unquoted = _vault(tmp_path / "other", "**/specs")
    assert [i.code for i in load_definitions(unquoted).issues] == ["schema-invalid-yaml"]


def test_empty_path_key_means_no_constraint(tmp_path: Path) -> None:
    root = _vault(tmp_path, "")
    loaded = load_definitions(root)
    assert loaded.issues == []
    assert loaded.schemas["episode"].entity_paths == ()


def test_pattern_that_matches_no_folder_is_valid(tmp_path: Path) -> None:
    root = _vault(tmp_path, "nowhere/**")
    assert load_definitions(root).issues == []


def test_no_path_means_anywhere(tmp_path: Path) -> None:
    root = _vault(tmp_path, None)
    _entity(root, "a.md")
    _entity(root, "deep/er/b.md")
    assert Knott.open(root).validate().issues == []


def test_misplaced_entity(tmp_path: Path) -> None:
    root = _vault(tmp_path, "episodes/*")
    _entity(root, "episodes/2026/ok.md")
    _entity(root, "episodes/42.md")
    _entity(root, "notes/episode-42.md")
    _entity(root, "top.md")
    issues = Knott.open(root).validate().issues
    assert [(i.path, i.line, i.field, i.code) for i in issues] == [
        ("episodes/42.md", 3, None, "entity-misplaced"),
        ("notes/episode-42.md", 3, None, "entity-misplaced"),
        ("top.md", 3, None, "entity-misplaced"),
    ]
    assert issues[1].message == (
        "`episode` entities are stored in `episodes/*`, but this file is in `notes`"
    )
    assert issues[2].message.endswith("but this file is in `.`")


def test_several_patterns_are_alternatives(tmp_path: Path) -> None:
    root = _vault(tmp_path, "[specs/, drafts/**, .]")
    for rel in ("specs/a.md", "drafts/b.md", "drafts/x/y/c.md", "d.md"):
        _entity(root, rel)
    _entity(root, "specs/old/e.md")
    issues = _misplaced(root)
    assert [i.path for i in issues] == ["specs/old/e.md"]
    assert "stored in `specs` or `drafts/**` or `.`, but" in issues[0].message


def test_other_checks_still_run_on_a_misplaced_entity(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    _write(
        root,
        ".knott/concepts/spec.md",
        "---\nname: spec\npath: specs\nproperties:\n"
        "  title: { type: string, required: true }\n---\n",
    )
    _write(root, "notes/a.md", "---\ntype: spec\n---\n")
    codes = [i.code for i in Knott.open(root).validate().issues]
    assert sorted(codes) == ["attribute-missing", "entity-misplaced"]


def test_path_says_nothing_about_other_files_in_the_folder(tmp_path: Path) -> None:
    root = _vault(tmp_path, "specs", name="spec")
    _write(root, ".knott/concepts/note.md", "---\nname: note\npath: specs\n---\n")
    _entity(root, "specs/a.md", "spec")
    _entity(root, "specs/b.md", "note")
    _write(root, "specs/plain.md", "no frontmatter\n")
    assert Knott.open(root).validate().issues == []


def test_scoped_run_reports_only_entities_in_scope(tmp_path: Path) -> None:
    root = _vault(tmp_path, "specs", name="spec")
    _entity(root, "specs/a.md", "spec")
    _entity(root, "notes/b.md", "spec")
    assert Knott.open(root).validate(["specs"]).issues == []
    assert [i.code for i in Knott.open(root).validate(["notes"]).issues] == ["entity-misplaced"]


def test_ontology_entity_paths(tmp_path: Path) -> None:
    root = _vault(tmp_path, "[specs, drafts/*]", name="spec")
    _write(root, ".knott/concepts/note.md", "---\nname: note\n---\n")
    by_type = {t.type: t for t in Knott.open(root).ontology().types}
    assert by_type["spec"].entity_paths == ["specs", "drafts/*"]
    assert by_type["note"].entity_paths == []


def test_types_verbose_prints_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(tmp_path, "[specs, drafts/*]", name="spec")
    _write(root, ".knott/concepts/note.md", "---\nname: note\n---\n")
    monkeypatch.chdir(root)
    out = runner.invoke(app, ["types", "--verbose"]).output
    assert "  template: no\n  path: specs | drafts/*\n  references: none" in out
    note = out.split("note  (")[1].split("spec  (")[0]
    assert "path:" not in note


def test_validate_prints_the_issue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _vault(tmp_path, "episodes/*")
    _entity(root, "notes/episode-42.md")
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert (
        "✗ notes/episode-42.md:3\n"
        "  `episode` entities are stored in `episodes/*`, but this file is in `notes`\n"
    ) in result.output


def test_view_embeds_entity_paths(tmp_path: Path) -> None:
    root = _vault(tmp_path, "episodes/*")
    html = render_ontology(Knott.open(root).ontology())
    assert '"entity_paths": ["episodes/*"]' in html or '"entity_paths":["episodes/*"]' in html
