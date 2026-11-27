"""`knott mv` and `Knott.move()` (spec 0018)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import Knott, KnottError, MoveError, MoveResult
from knott.cli import app
from knott.vault import fix as fix_module
from knott.vault.move import body_links, relative_path

from .conftest import FIXTURES

runner = CliRunner()

K1 = "11111111-1111-4111-8111-111111111111"
DOCS = FIXTURES.parent.parent / "docs"

CONCEPT = "---\nname: concept\npath: concepts\nproperties:\n  title: { type: string }\n---\n"
NOTE = """---
name: note
filename:
  pattern: "{slug}"
  parts:
    slug: { match: "[a-z0-9-]+" }
properties:
  about: { type: reference, target: concept }
  related:
    type: list
    items: { type: reference, relation: related, target: [concept, note] }
  steps:
    type: list
    items: { type: object, fields: { who: { type: reference, target: concept } } }
  audio: { type: file }
  slides: { type: file }
  ratio: { type: number }
---
See [the template](../../concepts/a.md).
"""
RELATED = "---\nname: related\nsymmetric: true\n---\nSee [A](../../concepts/a.md) for an example.\n"


def _write(root: Path, rel: str, text: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_bytes().decode("utf-8")


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "vault"
    _write(root, ".knott/concepts/concept.md", CONCEPT)
    _write(root, ".knott/concepts/note.md", NOTE)
    _write(root, ".knott/relations/related.md", RELATED)
    _write(root, ".knott/connectors/s3.md", "---\nname: s3\n---\n")
    _write(
        root, "concepts/a.md", f"---\ntype: concept\nkid: {K1}\ntitle: A\n---\nSelf: [A](a.md).\n"
    )
    _write(root, "concepts/b.md", "---\ntype: concept\ntitle: B\n---\n")
    _write(root, "audio/ep.mp3", "x")
    _write(root, "img/pic.png", "x")
    _write(
        root,
        "notes/n1.md",
        """---
type: note
about: ../concepts/a.md   # the subject
related:
  - "[A](../concepts/a.md)"
  - '../concepts/a.md'
  - "kid:11111111-1111-4111-8111-111111111111"
  - [not, a, reference]
steps:
  - who: "[A](<../concepts/a.md>)"
audio: ../audio/ep.mp3
slides: s3://talks/ep.pdf
undeclared: ../concepts/a.md
ratio: .nan
---
# Note

Inline [A](../concepts/a.md), with a fragment [usage](../concepts/a.md#usage "Usage"),
wrapped [A](<../concepts/a.md>), an image ![pic](../img/pic.png) and [B](../concepts/b.md).

Not links: `[A](../concepts/a.md)`, [[../concepts/a.md]], <../concepts/a.md>,
[web](https://example.com/concepts/a.md), [case](../concepts/A.md), [gone](../concepts/gone.md).

```
[A](../concepts/a.md)
```

~~~md
[A](../concepts/a.md)
~~~

<!-- [A](../concepts/a.md) -->

[ref]: ../concepts/a.md
""",
    )
    _write(root, "notes/plain.md", "Plain note with [A](../concepts/a.md).\n")
    _write(
        root,
        "notes/untyped.md",
        "---\ntype: ghost\nabout: ../concepts/a.md\n---\n[A](../concepts/a.md)\n",
    )
    _write(root, "notes/broken.md", "---\ntype: [\n---\n[A](../concepts/a.md)\n")
    _write(root, ".hidden/x.md", "[A](../concepts/a.md)\n")
    monkeypatch.chdir(root)
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _mv(*args: str) -> str:
    result = runner.invoke(app, ["mv", *args])
    assert result.exit_code == 0, result.output
    return result.stdout


def _fails(*args: str) -> str:
    result = runner.invoke(app, ["mv", *args])
    assert result.exit_code == 2, result.output
    assert result.stdout == ""
    return result.stderr


# --- a rename -------------------------------------------------------------------


def test_rename_rewrites_every_link_and_nothing_else(vault: Path) -> None:
    before = _snapshot(vault)
    output = _mv("concepts/a.md", "concepts/alpha.md")
    assert (
        output
        == (
            "moved concepts/a.md → concepts/alpha.md\n"
            "\n"
            "updated 12 links in 5 files\n"
            "  .knott/relations/related.md:5  body\n"
            "  concepts/alpha.md:6            body\n"
            "  notes/n1.md:3                  about\n"
            "  notes/n1.md:5                  related[0]\n"
            "  notes/n1.md:6                  related[1]\n"
            "  notes/n1.md:10                 steps[0].who\n"
            "  notes/n1.md:18                 body\n"
            "  notes/n1.md:18                 body\n"
            "  notes/n1.md:19                 body\n"
            "  notes/n1.md:32                 body\n"
            "  notes/plain.md:1               body\n"
            "  notes/untyped.md:5             body\n"
            "\n"
            "skipped 1 file\n"
            "  notes/broken.md  cannot read the frontmatter: "
        )
        + output.split("cannot read the frontmatter: ")[1]
    )
    after = _snapshot(vault)
    assert "concepts/a.md" not in after
    assert after["concepts/alpha.md"] == before["concepts/a.md"].replace(b"(a.md)", b"(alpha.md)")
    n1 = after["notes/n1.md"].decode()
    assert "about: ../concepts/alpha.md   # the subject\n" in n1
    assert '  - "[A](../concepts/alpha.md)"\n' in n1
    assert "  - '../concepts/alpha.md'\n" in n1
    assert '  - who: "[A](<../concepts/alpha.md>)"\n' in n1
    assert f'  - "kid:{K1}"\n' in n1  # a kid reference still points at the entity
    assert "undeclared: ../concepts/a.md\n" in n1  # knott cannot tell a path from a string
    assert "Inline [A](../concepts/alpha.md), with a fragment" in n1
    assert '[usage](../concepts/alpha.md#usage "Usage"),' in n1
    assert "wrapped [A](<../concepts/alpha.md>), an image ![pic](../img/pic.png)" in n1
    assert "<!-- [A](../concepts/alpha.md) -->" in n1  # an HTML comment is not special
    # code, wikilinks, autolinks, URLs, another case, reference definitions: as written
    for kept in (
        "`[A](../concepts/a.md)`, [[../concepts/a.md]], <../concepts/a.md>,",
        "[web](https://example.com/concepts/a.md), [case](../concepts/A.md)",
        "```\n[A](../concepts/a.md)\n```",
        "~~~md\n[A](../concepts/a.md)\n~~~",
        "[ref]: ../concepts/a.md",
    ):
        assert kept in n1, kept
    # every changed line is a reported one, and no other file changed
    changed = {
        (path, i + 1)
        for path in before.keys() & after.keys()
        for i, (old, new) in enumerate(
            zip(before[path].split(b"\n"), after[path].split(b"\n"), strict=True)
        )
        if old != new
    }
    reported = {
        (line.split(":")[0].strip(), int(line.split(":")[1].split()[0]))
        for line in output.split("\n\n")[1].splitlines()[1:]
        if not line.strip().startswith("concepts/alpha.md")
    }
    assert changed == reported
    assert after["notes/untyped.md"].startswith(b"---\ntype: ghost\nabout: ../concepts/a.md\n")
    assert after["notes/broken.md"] == before["notes/broken.md"]
    assert after[".hidden/x.md"] == before[".hidden/x.md"]
    assert after[".knott/concepts/note.md"] == before[".knott/concepts/note.md"]  # a template


def test_refs_and_validate_agree_after_a_move(vault: Path) -> None:
    (vault / "notes/broken.md").unlink()
    knott = Knott.open(vault)
    codes_before = sorted((i.path, i.code) for i in knott.validate().issues)
    refs_before = knott.refs("concepts/a.md").groups
    result = knott.move("concepts/a.md", "concepts/deep/alpha.md")
    assert isinstance(result, MoveResult)
    assert result.kid == K1
    assert knott.refs("concepts/deep/alpha.md").groups == refs_before
    moved = [("concepts/deep/alpha.md", "entity-misplaced")]
    assert sorted((i.path, i.code) for i in knott.validate().issues) == sorted(codes_before + moved)
    assert [i.code for i in result.issues] == ["entity-misplaced"]


# --- the moved file's own links ---------------------------------------------------


def test_folder_change_rewrites_the_files_own_links(vault: Path) -> None:
    output = _mv("notes/n1.md", "archive/2026/n1.md")
    assert "moved notes/n1.md → archive/2026/n1.md\n" in output
    n1 = _read(vault, "archive/2026/n1.md")
    assert "about: ../../concepts/a.md   # the subject\n" in n1
    assert '  - "[A](../../concepts/a.md)"\n' in n1
    assert "  - '../../concepts/a.md'\n" in n1
    assert "audio: ../../audio/ep.mp3\n" in n1  # a file property reaches the same file
    assert "slides: s3://talks/ep.pdf\n" in n1  # not a path
    assert "an image ![pic](../../img/pic.png) and [B](../../concepts/b.md)." in n1
    assert "[web](https://example.com/concepts/a.md), [case](../concepts/A.md)" in n1
    assert "unchanged 2 links\n" in output
    assert "  archive/2026/n1.md:22  body  `../concepts/A.md` does not exist\n" in output
    assert "  archive/2026/n1.md:22  body  `../concepts/gone.md` does not exist\n" in output
    assert not (vault / "notes/n1.md").exists()
    assert (vault / "notes").is_dir()  # an emptied or not, the source folder stays
    knott = Knott.open(vault)
    assert [g.label for g in knott.refs("concepts/a.md").groups]  # still referenced
    assert knott.show("archive/2026/n1.md").references[0].path == "concepts/a.md"


def test_rename_in_the_same_folder_leaves_the_files_other_links(vault: Path) -> None:
    (vault / "notes/broken.md").unlink()
    before = _read(vault, "notes/n1.md")
    output = _mv("notes/n1.md", "notes/first.md")
    assert output == "moved notes/n1.md → notes/first.md\n\nno links to update\n"
    assert _read(vault, "notes/first.md") == before


def test_move_into_an_existing_folder(vault: Path) -> None:
    (vault / "archive").mkdir()
    assert _mv("notes/plain.md", "archive").startswith("moved notes/plain.md → archive/plain.md\n")
    assert _read(vault, "archive/plain.md") == "Plain note with [A](../concepts/a.md).\n"
    result = json.loads(_mv("archive/plain.md", "plain.md", "--format", "json"))
    assert result["kid"] is None
    assert result["updated"] == [
        {
            "path": "plain.md",
            "line": 1,
            "field": None,
            "old": "../concepts/a.md",
            "new": "concepts/a.md",
        }
    ]


# --- how a link is rewritten -----------------------------------------------------


@pytest.mark.parametrize(
    ("dest", "about", "link", "wrapped"),
    [
        (
            "concepts/new name.md",
            "../concepts/new name.md",
            "new%20name.md",
            "<../concepts/new name.md>",
        ),
        ("concepts/a (1).md", "../concepts/a (1).md", "a%20%281%29.md", "<../concepts/a (1).md>"),
        ("concepts/100%.md", "../concepts/100%.md", "100%25.md", "<../concepts/100%25.md>"),
        ("concepts/a: b.md", '"../concepts/a: b.md"', "a:%20b.md", "<../concepts/a: b.md>"),
        ("concepts/it's.md", "../concepts/it's.md", "it's.md", "<../concepts/it's.md>"),
    ],
)
def test_new_names_are_written_so_they_read_back(
    vault: Path, dest: str, about: str, link: str, wrapped: str
) -> None:
    (vault / "notes/broken.md").unlink()
    knott = Knott.open(vault)
    issues_before = [(i.path, i.field, i.code) for i in knott.validate().issues]
    _mv("concepts/a.md", dest)
    n1 = _read(vault, "notes/n1.md")
    # a plain value stays plain while it still reads as the same string, else double quotes
    assert f"about: {about}   # the subject\n" in n1
    assert f"Inline [A](../concepts/{link})" in n1
    assert f"wrapped [A]({wrapped})" in n1
    assert [(i.path, i.field, i.code) for i in knott.validate().issues] == issues_before
    detail = knott.show("notes/n1.md")
    assert {r.path for r in detail.references if r.field != "related[3]"} == {dest}


def test_single_quoted_value_doubles_a_quote(vault: Path) -> None:
    _mv("concepts/a.md", "concepts/it's.md")
    assert "  - '../concepts/it''s.md'\n" in _read(vault, "notes/n1.md")


def test_first_segment_with_a_colon_gets_a_dot_slash(vault: Path) -> None:
    _write(vault, "concepts/c.md", '---\ntype: concept\n---\n[A](a.md) and "x"\n')
    _write(vault, "concepts/n.md", '---\ntype: note\nabout: a.md\nrelated: ["[A](a.md)"]\n---\n')
    _mv("concepts/a.md", "concepts/a:b.md")
    assert "[A](./a:b.md)" in _read(vault, "concepts/c.md")
    n = _read(vault, "concepts/n.md")
    assert "about: ./a:b.md\n" in n
    assert 'related: ["[A](./a:b.md)"]' in n
    assert relative_path("x/a:b.md", "y/n.md") == "../x/a:b.md"  # only a first segment


def test_flow_list_and_escapes(vault: Path) -> None:
    _write(
        vault,
        "notes/flow.md",
        "---\ntype: note\nrelated: [../concepts/a.md, ../concepts/b.md]\n---\n",
    )
    _mv("concepts/a.md", "concepts/a, b.md")
    assert 'related: ["../concepts/a, b.md", ../concepts/b.md]\n' in _read(vault, "notes/flow.md")


def test_bytes_are_kept(vault: Path) -> None:
    text = (
        "﻿---\r\ntype: note\r\nabout:   ../concepts/a.md  \r\n---\r\n\r\n[A](../concepts/a.md)  \r\n"
    )
    _write(vault, "notes/crlf.md", text)
    os.chmod(vault / "notes/crlf.md", 0o640)
    _mv("concepts/a.md", "concepts/alpha.md")
    assert _read(vault, "notes/crlf.md") == text.replace("a.md", "alpha.md")
    assert (vault / "notes/crlf.md").stat().st_mode & 0o777 == 0o640
    os.chmod(vault / "notes/crlf.md", 0o600)
    _mv("notes/crlf.md", "notes/deep/crlf.md")
    assert _read(vault, "notes/deep/crlf.md") == text.replace(
        "../concepts/a.md", "../../concepts/alpha.md"
    )
    assert (vault / "notes/deep/crlf.md").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    ("frontmatter", "problem"),
    [
        ("about: >\n  ../concepts/a.md\n", "block scalar"),
        ('about: "../concepts/a\\\n  .md"\n', "several lines"),
        ("x: &a ../concepts/a.md\nabout: *a\n", "alias"),
        ("base: &b {about: ../concepts/a.md}\n<<: *b\n", "alias"),
    ],
)
def test_a_value_that_cannot_be_edited_in_place_refuses_the_move(
    vault: Path, frontmatter: str, problem: str
) -> None:
    _write(vault, "notes/odd.md", f"---\ntype: note\n{frontmatter}---\n")
    assert Knott.open(vault).validate(["notes/odd.md"]).ok
    before = _snapshot(vault)
    error = _fails("concepts/a.md", "concepts/alpha.md")
    assert "cannot rewrite `about` in notes/odd.md in place" in error
    assert problem in error
    assert _snapshot(vault) == before


# --- SOURCE and DEST ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("concepts/a.md", "concepts/b.md"), "DEST already exists"),
        (("concepts/a.md", "concepts/a.md"), "the same file"),
        (("concepts/a.md", "concepts/./a.md"), "the same file"),
        (("concepts/a.md", "archive/"), "does not end in `.md`"),
        (("concepts/a.md", "concepts/a.txt"), "does not end in `.md`"),
        (("concepts/a.md", "concepts/b.md/a.md"), "under a file"),
        (("concepts/a.md", ".knott/a.md"), "hidden folder"),
        (("concepts/a.md", ".obsidian/a.md"), "hidden folder"),
        (("concepts/a.md", "concepts/b#1.md"), "`#`"),
        (("concepts/a.md", "../outside.md"), "outside the vault"),
        (("concepts/nope.md", "concepts/x.md"), "path does not exist"),
        (("notes/broken.md", "notes/fixed.md"), "cannot read the frontmatter"),
        ((".knott/concepts/note.md", "note.md"), "not a Markdown file knott sees"),
        (("audio/ep.mp3", "audio/ep.md"), "not a Markdown file knott sees"),
        (("kid:nope", "x.md"), "kid"),
    ],
)
def test_usage_errors_write_nothing(vault: Path, args: tuple[str, ...], message: str) -> None:
    before = _snapshot(vault)
    assert message in _fails(*args)
    assert _snapshot(vault) == before


def test_symbolic_links_are_not_followed(vault: Path, tmp_path: Path) -> None:
    (vault / "concepts/link.md").symlink_to(vault / "concepts/b.md")
    assert "symbolic link" in _fails("concepts/link.md", "concepts/x.md")
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / "out").symlink_to(outside, target_is_directory=True)
    assert "outside the vault" in _fails("concepts/b.md", "out/b.md")
    assert not (outside / "b.md").exists()


def test_symlinked_referring_file_is_skipped_not_replaced(vault: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("[A](concepts/a.md)\n", encoding="utf-8")
    (vault / "linked.md").symlink_to(outside)
    output = _mv("concepts/a.md", "concepts/alpha.md")
    assert "  linked.md        is a symbolic link, which knott does not edit\n" in output
    assert (vault / "linked.md").is_symlink()
    assert outside.read_text(encoding="utf-8") == "[A](concepts/a.md)\n"


def test_file_property_that_names_the_moved_file(vault: Path) -> None:
    _write(vault, "notes/n2.md", '---\ntype: note\naudio: "[notes](plain.md)"\n---\n')
    output = _mv("notes/plain.md", "archive/plain.md")
    assert "  notes/n2.md:3  audio\n" in output
    assert 'audio: "[notes](../archive/plain.md)"\n' in _read(vault, "notes/n2.md")


def test_failed_write_of_dest_leaves_no_partial_file(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    real_open = open

    class Failing(io.BytesIO):
        def write(self, data: object) -> int:
            raise OSError(28, "No space left on device")

    def fake_open(path: object, mode: str = "r", *args: object, **kwargs: object) -> object:
        if mode == "xb":
            real_open(path, mode).close()  # type: ignore[call-overload]
            return Failing()
        return real_open(path, mode, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr("builtins.open", fake_open)
    with pytest.raises(MoveError) as caught:
        Knott.open(vault).move("concepts/a.md", "concepts/alpha.md")
    monkeypatch.undo()
    assert caught.value.written == []
    assert (vault / "concepts/a.md").exists()
    assert not (vault / "concepts/alpha.md").exists()


def test_move_by_kid_and_relative_to_the_current_directory(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(vault / "concepts")
    assert _mv(f"kid:{K1}", "alpha.md").startswith("moved concepts/a.md → concepts/alpha.md\n")
    assert _mv("alpha.md", "../notes/alpha.md").startswith(
        "moved concepts/alpha.md → notes/alpha.md\n"
    )
    assert f"kid: {K1}\n" in _read(vault, "notes/alpha.md")


def test_case_only_rename(vault: Path) -> None:
    _write(vault, "notes/case.md", "[A](../concepts/a.md)\n[me](case.md)\n")
    _write(vault, "notes/other.md", "[c](case.md)\n")
    output = _mv("notes/case.md", "notes/Case.md")
    assert output.startswith("moved notes/case.md → notes/Case.md\n")
    assert "Case.md" in os.listdir(vault / "notes")
    assert "case.md" not in os.listdir(vault / "notes")
    assert _read(vault, "notes/Case.md") == "[A](../concepts/a.md)\n[me](Case.md)\n"
    assert _read(vault, "notes/other.md") == "[c](Case.md)\n"


def test_filename_and_path_warnings_do_not_stop_the_move(vault: Path) -> None:
    result = runner.invoke(app, ["mv", "notes/n1.md", "notes/N 1.md"])
    assert result.exit_code == 0
    assert result.stdout.startswith("moved notes/n1.md → notes/N 1.md\n")
    assert result.stderr.startswith("✗ notes/N 1.md:2\n")
    assert "files are named" in result.stderr
    assert (vault / "notes/N 1.md").exists()
    data = json.loads(_mv("concepts/b.md", "notes/b.md", "--format", "json", "--dry-run"))
    assert [i["code"] for i in data["issues"]] == ["entity-misplaced"]
    assert data["dry_run"] is True


# --- dry run, JSON, failures -------------------------------------------------------


def test_dry_run_writes_nothing_and_prints_the_same(vault: Path) -> None:
    before = _snapshot(vault)
    dry = _mv("concepts/a.md", "concepts/deep/alpha.md", "--dry-run")
    assert _snapshot(vault) == before
    assert not (vault / "concepts/deep").exists()
    real = _mv("concepts/a.md", "concepts/deep/alpha.md")
    assert dry.startswith(
        "would move concepts/a.md → concepts/deep/alpha.md\n\nwould update 12 links in 5 files\n"
    )
    assert dry.replace("would move", "moved").replace("would update", "updated") == real


def test_json(vault: Path) -> None:
    data = json.loads(_mv("concepts/a.md", "concepts/alpha.md", "--format", "json"))
    assert data["from"] == "concepts/a.md"
    assert "from_" not in data
    assert data["to"] == "concepts/alpha.md"
    assert data["kid"] == K1
    assert data["dry_run"] is False
    assert data["updated"][2] == {
        "path": "notes/n1.md",
        "line": 3,
        "field": "about",
        "old": "../concepts/a.md",
        "new": "../concepts/alpha.md",
    }
    assert {
        "path": "notes/n1.md",
        "line": 19,
        "field": None,
        "old": "../concepts/a.md",
        "new": "../concepts/alpha.md",
    } in data["updated"]
    assert {
        "path": "notes/n1.md",
        "line": 18,
        "field": None,
        "old": "../concepts/a.md#usage",
        "new": "../concepts/alpha.md#usage",
    } in data["updated"]
    assert data["unchanged"] == [] and data["issues"] == []
    assert [s["path"] for s in data["skipped"]] == ["notes/broken.md"]


def test_io_error_leaves_both_copies_and_names_what_was_written(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_write = fix_module._write_atomic
    calls: list[Path] = []

    def failing(path: Path, text: str) -> None:
        calls.append(path)
        if len(calls) == 2:
            raise OSError(28, "No space left on device", str(path))
        real_write(path, text)

    monkeypatch.setattr("knott.vault.move._write_atomic", failing)
    with pytest.raises(MoveError) as caught:
        Knott.open(vault).move("concepts/a.md", "concepts/alpha.md")
    assert caught.value.written == ["concepts/alpha.md", ".knott/relations/related.md"]
    assert "No space left on device" in str(caught.value)
    assert (vault / "concepts/a.md").exists() and (vault / "concepts/alpha.md").exists()
    monkeypatch.setattr("knott.vault.move._write_atomic", real_write)
    assert runner.invoke(app, ["mv", "concepts/b.md", "concepts/a.md"]).exit_code == 2


def test_legacy_layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    shutil.copytree(FIXTURES / "legacy-layout", root)
    monkeypatch.chdir(root)
    entity = next(p for p in sorted(Path().rglob("*.md")) if ".knott" not in p.parts)
    before = _snapshot(root)
    result = runner.invoke(app, ["mv", str(entity), "moved.md"])
    assert result.exit_code == 1
    assert result.stderr.startswith("✗ .knott/schemas\n")
    assert _snapshot(root) == before


def test_api_errors(vault: Path) -> None:
    knott = Knott.open(vault)
    with pytest.raises(KnottError):
        knott.move("concepts/a.md", "concepts/b.md")
    with pytest.raises(KnottError):
        knott.move("concepts/nope.md", "x.md")
    result = knott.move("concepts/b.md", "concepts/beta.md", dry_run=True)
    assert result.dry_run and result.from_ == "concepts/b.md"
    assert result.model_dump(mode="json", by_alias=True)["from"] == "concepts/b.md"


# --- the body scanner ------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[a](x.md)", ["x.md"]),
        ("![a](x.png) [b](<y z.md>)", ["x.png", "y z.md"]),
        ("[a](x.md#f 'T') [b](y.md \"T\") [c](z.md (T))", ["x.md", "y.md", "z.md"]),
        ("[![alt](i.png)](page.md)", ["i.png", "page.md"]),
        ("[a](x(1).md)", ["x(1).md"]),
        ("[a](x%20y.md)", ["x y.md"]),
        ("`[a](x.md)` ``[b](y.md)`` [c](z.md)", ["z.md"]),
        ("a ` lone backtick [a](x.md)", ["x.md"]),
        ("`open\n\n[a](x.md) `", ["x.md"]),  # a code span does not cross a blank line
        ("\\[a](x.md) [a\\](y.md)", ["x.md"]),
        ("[a](x.md", []),
        ("[a](x.md junk)", []),
        ("```\n[a](x.md)\n```\n[b](y.md)", ["y.md"]),
        ("````\n```\n[a](x.md)\n````\n[b](y.md)", ["y.md"]),
        ("~~~\n[a](x.md)\n```\n[b](y.md)\n~~~", []),
        ("```\n[a](x.md)\n", []),  # an unclosed fence runs to the end
        ("    [a](x.md)", ["x.md"]),  # indented code is not recognised
        ("[a]: x.md\n<x.md>\n[[x.md]]", []),
    ],
)
def test_body_links(text: str, expected: list[str]) -> None:
    assert [link.path for link in body_links(text, 0)] == expected


# --- the docs vault ----------------------------------------------------------------


@pytest.fixture
def docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "docs"
    shutil.copytree(DOCS, root, ignore=shutil.ignore_patterns(".obsidian", ".DS_Store"))
    monkeypatch.chdir(root)
    return root


def test_docs_rename_keeps_the_vault_valid(docs: Path) -> None:
    knott = Knott.open(docs)
    assert knott.validate().ok
    refs_before = knott.refs("specs/0006-relation-definitions.md").groups
    output = _mv("specs/0006-relation-definitions.md", "specs/0006-relations.md")
    for line in (
        "  README.md:",  # the README grows, so no line number
        "  specs/0007-view-inline-relations.md:13 ",
        "  specs/0013-concept-inheritance.md:20 ",
        "  specs/0014-open-reference-targets.md:19 ",
    ):
        assert line in output
    assert "concepts/ontology.md" not in output  # it names the file in a code span
    assert knott.validate().ok
    assert knott.refs("specs/0006-relations.md").groups == refs_before


def test_docs_folder_move_fixes_the_guides_own_links(docs: Path) -> None:
    knott = Knott.open(docs)
    before = knott.show("guides/obsidian.md")
    (docs / "guides/tools").mkdir()
    result = runner.invoke(app, ["mv", "guides/obsidian.md", "guides/tools/"])
    assert result.exit_code == 0
    assert "entity-misplaced" not in result.stdout
    assert "`guide` entities are stored in `guides`" in result.stderr
    after = knott.show("guides/tools/obsidian.md")
    assert [r.path for r in after.references] == [r.path for r in before.references]
    assert all(r.error is None for r in after.references)
    assert [i.code for i in knott.validate().issues] == ["entity-misplaced"]
