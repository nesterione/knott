from __future__ import annotations

import json
import re
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import Knott
from knott.cli import app
from knott.vault.fix import insert_kid

KID = "3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")

runner = CliRunner()


def _vault(tmp_path: Path, schema: str = "type: note\nkid: required\n") -> Path:
    Knott.init(tmp_path)
    (tmp_path / ".knott/schemas/note.yaml").write_text(schema)
    return tmp_path


def _write(vault: Path, name: str, data: bytes) -> Path:
    path = vault / name
    path.write_bytes(data)
    return path


def test_inserts_one_line_after_type_and_keeps_everything_else(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    original = (
        b"---\n"
        b"# a comment that must survive\n"
        b"type: note   # trailing comment\n"
        b"title: 'single quoted'\n"
        b"tags: [a,   b]\n"
        b"---\n"
        b"# Body\n\nText.\n"
    )
    path = _write(vault, "a.md", original)
    assert insert_kid(vault, "a.md", KID)
    lines = original.split(b"\n")
    lines.insert(3, f"kid: {KID}".encode())
    assert path.read_bytes() == b"\n".join(lines)


def test_keeps_crlf_and_bom(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = _write(vault, "a.md", b"\xef\xbb\xbf---\r\ntype: note\r\n---\r\nBody\r\n")
    assert insert_kid(vault, "a.md", KID)
    assert path.read_bytes() == (
        b"\xef\xbb\xbf---\r\ntype: note\r\nkid: " + KID.encode() + b"\r\n---\r\nBody\r\n"
    )


def test_falls_back_to_before_the_closing_delimiter(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    # A folded block scalar: a line right after `type:` would land inside it.
    path = _write(vault, "a.md", b"---\ntype: >-\n  note\ntitle: x\n---\n")
    assert insert_kid(vault, "a.md", KID)
    assert path.read_text() == f"---\ntype: >-\n  note\ntitle: x\nkid: {KID}\n---\n"


def test_refuses_when_no_position_keeps_the_frontmatter(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    original = b"---\n{type: note, title: x}\n---\n"
    path = _write(vault, "a.md", original)
    assert not insert_kid(vault, "a.md", KID)
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "text",
    [
        "---\ntype: note\nkid:\n---\n",  # present but empty: left for a human
        f"---\ntype: note\nkid: {KID.upper()}\n---\n",  # present but invalid
        "---\ntitle: no type\n---\n",  # not an entity
        "# no frontmatter\n",
        "---\ntype: [unclosed\n---\n",  # invalid frontmatter
    ],
)
def test_leaves_files_it_must_not_touch(tmp_path: Path, text: str) -> None:
    vault = _vault(tmp_path)
    path = _write(vault, "a.md", text.encode())
    assert not insert_kid(vault, "a.md", KID)
    assert path.read_text() == text


def test_keeps_file_mode(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = _write(vault, "a.md", b"---\ntype: note\n---\n")
    path.chmod(0o640)
    assert insert_kid(vault, "a.md", KID)
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert [p.name for p in vault.iterdir() if p.name.endswith(".tmp")] == []


def test_does_not_write_through_a_symlink_out_of_the_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _vault(vault)
    outside = tmp_path / "outside.md"
    outside.write_text("---\ntype: note\n---\n")
    (vault / "link.md").symlink_to(outside)
    assert not insert_kid(vault, "link.md", KID)
    assert outside.read_text() == "---\ntype: note\n---\n"


def test_validate_fix_assigns_then_validates(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write(vault, "a.md", b"---\ntype: note\n---\n")
    _write(vault, "b.md", f"---\ntype: note\nkid: {KID}\n---\n".encode())
    _write(vault, "plain.md", b"# just a note\n")
    knott = Knott.open(vault)
    assert [i.code for i in knott.validate().issues] == ["kid-missing"]
    result = knott.validate(fix=True)
    assert result.ok, result.issues
    assert [f.path for f in result.fixed] == ["a.md"]
    assert UUID.fullmatch(result.fixed[0].kid)
    assert f"kid: {result.fixed[0].kid}\n" in (vault / "a.md").read_text()
    # Idempotent: nothing left to fix.
    assert knott.validate(fix=True).fixed == []


def test_validate_fix_respects_scope_and_optional_types(tmp_path: Path) -> None:
    vault = _vault(tmp_path, "type: note\n")
    _write(vault, "a.md", b"---\ntype: note\n---\n")
    _write(vault, "b.md", b"---\ntype: note\n---\n")
    result = Knott.open(vault).validate(["b.md"], fix=True)
    # `kid` is optional for this type, but knott still gives every fixed entity one.
    assert [f.path for f in result.fixed] == ["b.md"]
    assert "kid" not in (vault / "a.md").read_text()


def test_cli_fix_text_and_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = _vault(tmp_path)
    _write(vault, "a.md", b"---\ntype: note\n---\n")
    monkeypatch.chdir(vault)
    result = runner.invoke(app, ["validate", "--fix"])
    assert result.exit_code == 0
    assert result.output.startswith("+ kid  a.md\n\n✓ 1 schema\n")

    _write(vault, "b.md", b"---\ntype: note\n---\n")
    result = runner.invoke(app, ["validate", "--fix", "--format", "json"])
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert [f["path"] for f in payload["fixed"]] == ["b.md"]

    # Without --fix, nothing is written and the JSON has no `fixed` key.
    _write(vault, "c.md", b"---\ntype: note\n---\n")
    result = runner.invoke(app, ["validate", "--format", "json"])
    assert result.exit_code == 1
    assert "fixed" not in json.loads(result.output)
    assert "kid" not in (vault / "c.md").read_text()


def test_fix_does_not_change_duplicates(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    text = f"---\ntype: note\nkid: {KID}\n---\n"
    _write(vault, "a.md", text.encode())
    _write(vault, "b.md", text.encode())
    result = Knott.open(vault).validate(fix=True)
    assert result.fixed == []
    assert [i.code for i in result.issues] == ["kid-duplicate"]
    assert (vault / "b.md").read_text() == text
