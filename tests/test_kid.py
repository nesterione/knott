from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import Issue, Knott
from knott.cli import app
from knott.vault import kid as kid_module
from knott.vault.kid import is_canonical, kid_problem
from knott.vault.links import LinkError, resolve_reference

from .conftest import fixture_path, validate_fixture

A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
HEX = "3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21"


def _kid_issues(issues: list[Issue]) -> list[tuple[str, int | None, str]]:
    return [(i.path, i.line, i.code) for i in issues if i.code.startswith("kid-")]


def test_kid_issues_in_fixture() -> None:
    result = validate_fixture("kid-identity")
    assert _kid_issues(result.issues) == [
        ("lexemes/draugas-copy.md", 3, "kid-duplicate"),
        ("lexemes/nokid.md", 2, "kid-missing"),
        ("lexemes/upper.md", 3, "kid-invalid"),
    ]
    by_code = {i.code: i for i in result.issues}
    assert by_code["kid-duplicate"].message.startswith(
        f"`kid` {A} is claimed by 2 entities: lexemes/draugas-copy.md:3, lexemes/draugas.md:3\n"
    )
    assert "knott validate --fix" in by_code["kid-missing"].message
    assert by_code["kid-invalid"].message.endswith("; write 33333333-3333-4333-8333-33333333333a")


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        (A, True),
        ("0192f4a1-7c3e-7b2a-9f10-3d5e8c2b4a61", True),  # v7 from another tool
        (HEX.upper(), False),
        ("{" + HEX + "}", False),
        (HEX.replace("-", ""), False),
        ("draugas", False),
        (42, False),
        (None, False),
    ],
)
def test_is_canonical(value: object, ok: bool) -> None:
    assert is_canonical(value) is ok


def test_kid_problem_suggests_the_canonical_form() -> None:
    assert kid_problem("{" + HEX.upper() + "}").endswith(f"; write {HEX}")
    assert "; write" not in kid_problem("draugas")
    assert "got integer `42`" in kid_problem(42)


def _vault(tmp_path: Path, files: dict[str, str], schema: str = "type: note\n") -> Path:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/note.yaml").write_text(schema)
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return tmp_path


def test_kid_is_optional_by_default_but_always_checked(tmp_path: Path) -> None:
    vault = _vault(
        tmp_path,
        {
            "a.md": "---\ntype: note\n---\n",
            "b.md": "---\ntype: note\nkid:\n---\n",
            "c.md": "---\ntype: note\nkid: 7\n---\n",
        },
    )
    result = Knott.open(vault).validate()
    assert [(i.path, i.code) for i in result.issues] == [("c.md", "kid-invalid")]


def test_empty_kid_on_required_type_points_at_its_line(tmp_path: Path) -> None:
    vault = _vault(
        tmp_path, {"a.md": "---\ntype: note\nkid: ''\n---\n"}, "type: note\nkid: required\n"
    )
    result = Knott.open(vault).validate()
    assert [(i.line, i.code) for i in result.issues] == [(3, "kid-missing")]


def test_duplicates_count_entities_of_any_type_but_not_plain_notes(tmp_path: Path) -> None:
    vault = _vault(
        tmp_path,
        {
            "a.md": f"---\ntype: note\nkid: {A}\n---\n",
            "b.md": f"---\ntype: unknown\nkid: {A}\n---\n",
            "c.md": f"---\nkid: {A}\n---\n",  # no type: not an entity
        },
    )
    result = Knott.open(vault).validate()
    duplicate = next(i for i in result.issues if i.code == "kid-duplicate")
    assert "a.md:3, b.md:3" in duplicate.message
    assert "c.md" not in duplicate.message


def test_scoped_run_reports_only_duplicates_it_touches(tmp_path: Path) -> None:
    vault = _vault(
        tmp_path,
        {
            "a.md": f"---\ntype: note\nkid: {A}\n---\n",
            "b.md": f"---\ntype: note\nkid: {A}\n---\n",
            "c.md": f"---\ntype: note\nkid: {B}\n---\n",
        },
    )
    knott = Knott.open(vault)
    assert knott.validate(["c.md"]).ok
    # In scope as the second claimant: the issue still sits on the first, naming both.
    issues = knott.validate(["b.md"]).issues
    assert [(i.path, i.code) for i in issues] == [("a.md", "kid-duplicate")]
    assert "b.md:3" in issues[0].message


def test_index_is_built_only_when_needed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    real = kid_module.build_index

    def counting(*args: object, **kwargs: object) -> kid_module.KidIndex:
        calls.append(1)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("knott.api.build_index", counting)
    vault = _vault(tmp_path, {"a.md": "---\ntype: note\n---\n"})
    Knott.open(vault).validate()
    assert calls == []
    (vault / "b.md").write_text(f"---\ntype: note\nkid: {A}\n---\n")
    (vault / "c.md").write_text(f"---\ntype: note\nkid: {B}\n---\n")
    Knott.open(vault).validate()
    assert calls == [1]  # once per run, however many entities have a kid


# --- kid: references ---------------------------------------------------------


def test_kid_references_in_fixture() -> None:
    result = validate_fixture("kid-identity")
    relation_issues = [(i.path, i.line, i.code) for i in result.issues if i.field == "includes"]
    assert relation_issues == [
        ("topics/broken.md", 5, "relation-target-ambiguous"),
        ("topics/broken.md", 6, "relation-target-not-found"),
        ("topics/broken.md", 7, "relation-target-type-mismatch"),
        ("topics/broken.md", 8, "relation-invalid-value"),
        ("topics/broken.md", 9, "relation-invalid-value"),
    ]
    messages = {i.line: i.message for i in result.issues if i.path == "topics/broken.md"}
    assert "fix the `kid-duplicate` first" in messages[5]
    assert messages[6] == (
        "relation `includes`: no entity has `kid` 55555555-5555-4555-8555-555555555555"
    )
    # The type mismatch names the kid as written and where it was found.
    assert "(`topics/broken.md`) has type `topic`" in messages[7]
    assert "cannot be a Markdown link" in messages[9]


def test_kid_reference_survives_a_move(copy_fixture: Callable[[str], Path]) -> None:
    vault = copy_fixture("kid-identity")
    home = ["topics/home.md"]
    assert Knott.open(vault).validate(home).stats.relations == 2
    (vault / "lexemes/archive/namas.md").rename(vault / "lexemes/namas-moved.md")
    issues = Knott.open(vault).validate(home).issues
    # The path reference breaks; the kid reference still resolves.
    assert [(i.line, i.code) for i in issues] == [(5, "relation-target-not-found")]


def test_kid_reference_accepts_surrounding_space(tmp_path: Path) -> None:
    vault = _vault(
        tmp_path,
        {
            "a.md": f"---\ntype: note\nkid: {A}\n---\n",
            "b.md": f'---\ntype: note\nsee: " kid: {A} "\n---\n',
        },
        "type: note\nrelations:\n  see:\n    target: note\n",
    )
    result = Knott.open(vault).validate()
    assert result.ok, result.issues
    assert result.stats.relations == 1


def test_resolve_reference_without_an_index_finds_no_kid(tmp_path: Path) -> None:
    with pytest.raises(LinkError) as caught:
        resolve_reference(tmp_path, "a.md", f"kid:{A}")
    assert caught.value.code == "relation-target-not-found"


def test_ontology_and_types_verbose_show_kid_required(monkeypatch: pytest.MonkeyPatch) -> None:
    ontology = Knott.open(fixture_path("kid-identity")).ontology()
    assert {t.type: t.kid_required for t in ontology.types} == {"lexeme": True, "topic": False}
    monkeypatch.chdir(fixture_path("kid-identity"))
    output = CliRunner().invoke(app, ["types", "--verbose"]).output
    assert output.startswith("lexeme  (.knott/schemas/lexeme.yaml)\n  kid: required\n")
    assert output.count("kid: required") == 1
