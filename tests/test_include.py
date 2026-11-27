"""The `include` key of `.knott/config.yaml` (spec 0019)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import ConfigError, Knott, KnottError
from knott.cli import app

from .conftest import FIXTURES, triples

runner = CliRunner()

K1 = "11111111-1111-4111-8111-111111111111"
K2 = "22222222-2222-4222-8222-222222222222"
DOCS = FIXTURES.parent.parent / "docs"
REASON = (
    "it is outside the included folders (`docs`); add its folder to `include` in .knott/config.yaml"
)

CONCEPT = "---\nname: concept\nproperties:\n  title: { type: string }\n---\n"
NOTE = """---
name: note
properties:
  about: { type: reference, target: concept }
  logo: { type: file }
---
"""


def _write(root: Path, rel: str, text: str | bytes) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))


def _note(about: str, extra: str = "") -> str:
    return f'---\ntype: note\nabout: "{about}"\n{extra}---\n'


def _include(root: Path, value: str) -> None:
    _write(root, ".knott/config.yaml", f"knott_version: 0.1.0\ninclude: {value}\n")


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vault"
    _write(root, ".knott/concepts/concept.md", CONCEPT)
    _write(root, ".knott/concepts/note.md", NOTE)
    _write(root, "docs/a.md", f"---\ntype: concept\nkid: {K1}\ntitle: A\n---\n")
    _write(root, "docs/n.md", _note("a.md"))
    _write(root, "docs/sub/deep.md", "---\ntype: concept\ntitle: Deep\n---\n")
    _write(root, "docs/.drafts/d.md", "---\ntype: concept\ntitle: Draft\n---\n")
    _write(root, "notes/plan.md", "---\ntype: concept\ntitle: Plan\n---\n")
    _write(root, "tests/b.md", f"---\ntype: concept\nkid: {K1}\ntitle: B\n---\n")
    _write(root, "tests/broken.md", "---\ntype: [\n---\n")
    _write(root, "tests/binary.md", b"---\ntype: \xff\n---\n")
    _write(root, "tests/unknown.md", "---\ntype: nothing\n---\n")
    _write(root, "README.md", "# Readme\n")
    _write(root, "assets/logo.png", "x")
    _include(root, "[docs]")
    monkeypatch.chdir(root)
    return root


def _codes(root: Path, paths: list[str] | None = None) -> list[tuple[str, int | None, str]]:
    return triples(Knott.open(root).validate(paths))


# --- the scanned set ------------------------------------------------------------


def test_without_the_key_the_whole_vault_is_scanned(vault: Path) -> None:
    _write(vault, ".knott/config.yaml", "knott_version: 0.1.0\n")
    opened = Knott.open(vault)
    assert opened.included_folders == (".",)
    result = opened.validate()
    assert result.stats.entities == 6
    assert {code for _, _, code in triples(result)} == {
        "entity-invalid-frontmatter",
        "entity-unknown-type",
        "kid-duplicate",
    }


def test_only_the_included_folders_are_validated(vault: Path) -> None:
    result = Knott.open(vault).validate()
    assert result.issues == []
    assert (result.stats.entities, result.stats.relations) == (3, 1)


def test_cli_validate_passes_and_counts(vault: Path) -> None:
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0
    assert "3 entities" in result.output


@pytest.mark.parametrize(
    ("value", "folders", "entities"),
    [
        ("docs", ("docs",), 3),
        ("[docs, docs/sub]", ("docs", "docs/sub"), 3),
        ("[docs/sub, docs]", ("docs/sub", "docs"), 3),
        ("[docs, docs]", ("docs",), 3),
        ("[docs/]", ("docs",), 3),
        ("[docs/sub]", ("docs/sub",), 1),
        ("[docs, notes]", ("docs", "notes"), 4),
        ("[assets]", ("assets",), 0),
    ],
)
def test_forms_of_the_value(
    vault: Path, value: str, folders: tuple[str, ...], entities: int
) -> None:
    _include(vault, value)
    opened = Knott.open(vault)
    assert opened.included_folders == folders
    assert len(opened.entities()) == entities


@pytest.mark.parametrize("value", [".", "./", "[., docs]", "[docs, .]"])
def test_the_root_is_the_whole_vault(vault: Path, value: str) -> None:
    _include(vault, value)
    assert Knott.open(vault).validate().stats.entities == 6


def test_a_root_file_is_scanned_only_with_the_root(vault: Path) -> None:
    _write(vault, "top.md", "---\ntype: concept\ntitle: Top\n---\n")
    assert "top.md" not in [e.path for e in Knott.open(vault).entities()]
    _include(vault, ".")
    assert "top.md" in [e.path for e in Knott.open(vault).entities()]


def test_hidden_folder_inside_an_included_folder_is_not_scanned(vault: Path) -> None:
    assert [e.path for e in Knott.open(vault).entities()] == [
        "docs/a.md",
        "docs/n.md",
        "docs/sub/deep.md",
    ]


def test_counts_in_the_ontology(vault: Path) -> None:
    counts = {t.type: t.count for t in Knott.open(vault).ontology().types}
    assert counts == {"concept": 2, "note": 1}


def test_files_outside_are_not_read(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    opened = Knott.open(vault)
    real = Path.read_bytes
    seen: list[str] = []

    def spy(self: Path) -> bytes:
        seen.append(self.relative_to(vault).as_posix())
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", spy)
    _write(vault, "docs/out.md", _note("../notes/plan.md"))
    opened.validate()
    opened.entities()
    opened.refs("docs/a.md")
    opened.show("docs/out.md")
    opened.ontology()
    opened.move("docs/a.md", "docs/z.md", dry_run=True)
    assert seen
    assert not [p for p in seen if p.startswith(("tests/", "notes/")) or p == "README.md"]


# --- kid --------------------------------------------------------------------------


def test_kid_outside_is_not_a_duplicate_and_resolves_inside(vault: Path) -> None:
    _write(vault, "docs/k.md", _note(f"kid:{K1}"))
    opened = Knott.open(vault)
    assert opened.validate().issues == []
    assert opened.refs(f"kid:{K1}").entity.path == "docs/a.md"


def test_kid_carried_only_outside_is_not_found(vault: Path) -> None:
    _write(vault, "notes/plan.md", f"---\ntype: concept\nkid: {K2}\ntitle: Plan\n---\n")
    _write(vault, "docs/k.md", _note(f"kid:{K2}"))
    assert _codes(vault) == [("docs/k.md", 3, "relation-target-not-found")]
    with pytest.raises(KnottError):
        Knott.open(vault).refs(f"kid:{K2}")


def test_fix_gives_no_kid_outside(vault: Path) -> None:
    before = (vault / "notes/plan.md").read_bytes()
    result = Knott.open(vault).validate(fix=True)
    assert [f.path for f in result.fixed] == ["docs/n.md", "docs/sub/deep.md"]
    assert (vault / "notes/plan.md").read_bytes() == before
    result = Knott.open(vault).validate(["notes/plan.md", "."], fix=True)
    assert result.fixed == []
    assert (vault / "notes/plan.md").read_bytes() == before


# --- reference targets --------------------------------------------------------------


def test_reference_to_a_file_outside_is_not_an_entity(vault: Path) -> None:
    _write(vault, "docs/out.md", _note("../notes/plan.md"))
    (issue,) = Knott.open(vault).validate().issues
    assert (issue.path, issue.line, issue.code) == ("docs/out.md", 3, "relation-target-not-entity")
    assert issue.message == (
        f"relation `about` points to `../notes/plan.md`, which is not a Knott entity: {REASON}"
    )


def test_reference_to_a_plain_file_outside_names_the_setting(vault: Path) -> None:
    _write(vault, "docs/out.md", _note("../README.md"))
    (issue,) = Knott.open(vault).validate().issues
    assert issue.code == "relation-target-not-entity"
    assert issue.message.endswith(REASON)


def test_reference_to_a_missing_file_outside_is_not_found(vault: Path) -> None:
    _write(vault, "docs/out.md", _note("../missing.md"))
    assert _codes(vault) == [("docs/out.md", 3, "relation-target-not-found")]


def test_reference_into_a_hidden_folder_inside_is_as_before(vault: Path) -> None:
    _write(vault, "docs/in.md", _note(".drafts/d.md"))
    _write(vault, "tests/.x/a.md", "---\ntype: concept\ntitle: X\n---\n")
    _write(vault, "docs/out.md", _note("../tests/.x/a.md"))
    assert _codes(vault) == [("docs/out.md", 3, "relation-target-not-entity")]


def test_file_property_may_point_outside(vault: Path) -> None:
    _write(vault, "docs/f.md", _note("a.md", 'logo: "../assets/logo.png"\n'))
    assert Knott.open(vault).validate().issues == []


def test_outside_target_is_no_reference_for_refs_show_and_list(vault: Path) -> None:
    _write(vault, "docs/out.md", _note("../notes/plan.md"))
    opened = Knott.open(vault)
    (ref,) = opened.show("docs/out.md").references
    assert (ref.path, ref.type, ref.error) == (
        "notes/plan.md",
        None,
        "relation-target-not-entity",
    )
    with pytest.raises(KnottError, match="outside the included folders"):
        opened.entities("note", where={"about": "notes/plan.md"})


# --- one named file -----------------------------------------------------------------


def test_validate_a_file_outside(vault: Path) -> None:
    result = Knott.open(vault).validate(["tests/b.md"])
    (issue,) = result.issues
    assert (issue.path, issue.code) == ("tests/b.md", "not-an-entity")
    assert issue.message == f"not a Knott entity: {REASON}"
    assert result.stats.entities == 0
    assert runner.invoke(app, ["validate", "tests/b.md"]).exit_code == 1


def test_validate_a_folder(vault: Path) -> None:
    assert Knott.open(vault).validate(["."]).stats.entities == 3
    outside = Knott.open(vault).validate(["tests"])
    assert (outside.issues, outside.stats.entities) == ([], 0)
    assert runner.invoke(app, ["validate", "tests/"]).exit_code == 0


def test_validate_a_file_in_a_hidden_folder_inside_is_as_before(vault: Path) -> None:
    result = Knott.open(vault).validate(["docs/.drafts/d.md"])
    assert (result.issues, result.stats.entities) == ([], 1)


@pytest.mark.parametrize("command", ["refs", "show"])
def test_refs_and_show_refuse_a_file_outside(vault: Path, command: str) -> None:
    result = runner.invoke(app, [command, "notes/plan.md"])
    assert result.exit_code == 2
    assert f"error: not a Knott entity: notes/plan.md; {REASON}" in result.output.replace("\n", " ")


@pytest.mark.parametrize("folder", ["docs", ".", "notes"])
def test_a_folder_is_not_called_outside(vault: Path, folder: str) -> None:
    for command in (["refs", folder], ["show", folder], ["mv", folder, "docs/x.md"]):
        result = runner.invoke(app, command)
        assert result.exit_code == 2
        assert "outside the included folders" not in result.output.replace("\n", " ")


def test_a_concept_path_outside_is_no_issue(vault: Path) -> None:
    _write(vault, ".knott/concepts/note.md", NOTE.replace("---\n", "---\npath: notes\n", 1))
    (vault / "docs/n.md").unlink()
    result = Knott.open(vault).validate()
    assert result.issues == []
    assert Knott.open(vault).schema_issues() == []


# --- loops, cycles, migrate ----------------------------------------------------------


def test_loop_board_holds_only_the_scanned_set(vault: Path) -> None:
    _write(
        vault,
        ".knott/concepts/concept.md",
        "---\nname: concept\nproperties:\n  title: { type: string }\n"
        "  status: { type: enum, options: [open, done] }\n---\n",
    )
    _write(
        vault,
        ".knott/loops/life.md",
        "---\nname: life\ntype: concept\nproperty: status\nstages:\n  open:\n  done:\n---\n",
    )
    _write(vault, "docs/a.md", "---\ntype: concept\ntitle: A\nstatus: open\n---\n")
    _write(vault, "notes/plan.md", "---\ntype: concept\ntitle: Plan\nstatus: open\n---\n")
    report = Knott.open(vault).loops("life")
    assert "notes/plan.md" not in json.dumps(report.model_dump(mode="json"))
    assert "docs/a.md" in json.dumps(report.model_dump(mode="json"))


def test_migrate_reads_only_the_scanned_set(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    _write(
        root,
        ".knott/schemas/note.yaml",
        "type: note\nrelations:\n  about: { target: note }\n",
    )
    _write(root, "docs/a.md", "---\ntype: note\nabout: b.md\n---\n")
    _write(root, "tests/b.md", "---\ntype: note\nabout: [a.md, c.md]\n---\n")
    _include(root, "[docs]")
    Knott.open(root).migrate()
    text = (root / ".knott/concepts/note.md").read_text(encoding="utf-8")
    assert "list" not in text


# --- mv -----------------------------------------------------------------------------


def test_mv_does_not_rewrite_a_link_outside(vault: Path) -> None:
    _write(vault, "notes/plan.md", "---\ntype: note\nabout: ../docs/a.md\n---\n[A](../docs/a.md)\n")
    before = (vault / "notes/plan.md").read_bytes()
    result = Knott.open(vault).move("docs/a.md", "docs/sub/a.md")
    assert [u.path for u in result.updated] == ["docs/n.md"]
    assert result.skipped == []
    assert (vault / "notes/plan.md").read_bytes() == before
    assert Knott.open(vault).validate().issues == []


def test_mv_refuses_a_source_outside(vault: Path) -> None:
    result = runner.invoke(app, ["mv", "notes/plan.md", "docs/plan.md"])
    assert result.exit_code == 2
    assert f"notes/plan.md; {REASON}" in result.output.replace("\n", " ")
    assert (vault / "notes/plan.md").exists()


@pytest.mark.parametrize("dry_run", [False, True])
def test_mv_refuses_a_destination_outside(vault: Path, dry_run: bool) -> None:
    with pytest.raises(
        KnottError, match=r"cannot move to notes/a\.md: the file would stop being an entity"
    ):
        Knott.open(vault).move("docs/a.md", "notes/a.md", dry_run=dry_run)
    with pytest.raises(KnottError, match="outside the included folders"):
        Knott.open(vault).move("docs/a.md", "notes", dry_run=dry_run)
    assert (vault / "docs/a.md").exists()
    assert not (vault / "notes/a.md").exists()


# --- checks on the value ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("[]", "expected a folder or a non-empty list of folders"),
        ("", "expected a folder or a non-empty list of folders"),
        ("3", "expected a folder or a non-empty list of folders"),
        ("{ a: b }", "expected a folder or a non-empty list of folders"),
        ("[docs, 3]", "each folder must be a string"),
        ('[""]', "a folder is empty"),
        ("[/docs]", "must be relative to the vault root"),
        ('["docs\\\\sub"]', "has a `\\`"),
        ('["docs/*"]', "folders are literal, not patterns"),
        ("[docs//sub]", "has an empty segment"),
        ("[./docs]", "has a `.` or `..` segment"),
        ("[docs/./sub]", "has a `.` or `..` segment"),
        ("[../shared]", "has a `.` or `..` segment"),
        ("[docs/../notes]", "has a `.` or `..` segment"),
        ("[.github]", "folder `.github` is hidden"),
        ("[docs/.drafts]", "folder `docs/.drafts` is hidden"),
        ("[doc]", "folder `doc` does not exist"),
        ("[docs/nope]", "folder `docs/nope` does not exist"),
        ("[Docs]", "folder `Docs` does not exist"),
        ("[README.md]", "`README.md` is not a folder"),
    ],
)
def test_invalid_values(vault: Path, value: str, message: str) -> None:
    _include(vault, value)
    with pytest.raises(ConfigError) as error:
        Knott.open(vault)
    assert str(error.value).startswith("invalid `include` in .knott/config.yaml:2: ")
    assert message in str(error.value)


def test_the_error_names_the_line_of_the_entry(vault: Path) -> None:
    _write(
        vault,
        ".knott/config.yaml",
        "knott_version: 0.1.0\ninclude:\n  - docs\n  - doc\n",
    )
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 2
    assert (
        "error: invalid `include` in .knott/config.yaml:4: folder `doc` does not exist"
        in result.output
    )


@pytest.mark.parametrize("entry", ["vendor", "vendor/inner", "docs/link"])
def test_a_symlinked_folder_is_refused(vault: Path, entry: str) -> None:
    _write(vault, "real/inner/x.md", "x")
    os.symlink(vault / "real", vault / "vendor")
    os.symlink(vault / "real", vault / "docs/link")
    _include(vault, f"[{entry}]")
    with pytest.raises(ConfigError, match="symbolic link"):
        Knott.open(vault)


@pytest.mark.parametrize(
    "command",
    [
        ["validate"],
        ["validate", "--fix"],
        ["types"],
        ["list"],
        ["show", "docs/a.md"],
        ["refs", "docs/a.md"],
        ["loops"],
        ["mv", "docs/a.md", "docs/z.md"],
        ["migrate"],
        ["view", "--no-open"],
    ],
)
def test_every_command_stops_on_an_invalid_value(vault: Path, command: list[str]) -> None:
    _include(vault, "[doc]")
    before = (vault / "docs/a.md").read_bytes()
    result = runner.invoke(app, command)
    assert result.exit_code == 2, result.output
    assert "invalid `include`" in result.output
    assert (vault / "docs/a.md").read_bytes() == before
    assert not (vault / "docs/z.md").exists()


# --- compatibility ---------------------------------------------------------------------


def test_the_docs_vault_is_the_same_with_the_root_included(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = tmp_path / "docs"
    shutil.copytree(DOCS, copy, ignore=shutil.ignore_patterns(".obsidian", ".DS_Store"))
    monkeypatch.chdir(copy)

    def outputs() -> list[str]:
        commands = [
            ["validate", "--format", "json"],
            ["types", "--verbose"],
            ["list", "--format", "json"],
            ["refs", "concepts/entity.md"],
            ["show", "specs/0019-included-folders.md"],
            ["mv", "concepts/entity.md", "concepts/thing.md", "--dry-run"],
        ]
        return [runner.invoke(app, c).output for c in commands]

    before = outputs()
    with (copy / ".knott/config.yaml").open("a", encoding="utf-8") as config:
        config.write("include: .\n")
    assert outputs() == before
