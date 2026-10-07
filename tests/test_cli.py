from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knott import version
from knott.cli import app

from .conftest import fixture_path

runner = CliRunner()

DOD_SCRIPT_SCHEMA = "type: script\nattributes:\n  title:\n    type: string\n    required: true\n"
DOD_TRANSCRIPT_SCHEMA = (
    "type: transcript\nrelations:\n  derived_from:\n    target: script\n"
    "    description: >\n      The script from which this transcript was produced.\n"
)
SUCCESS = "✓ 2 schemas\n✓ 2 entities\n✓ 1 relation\n✓ vault is valid\n"


@pytest.fixture
def dod_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The vault from the Definition of Done (spec §24)."""
    (tmp_path / ".knott/schemas").mkdir(parents=True)
    (tmp_path / ".knott/schemas/script.yaml").write_text(DOD_SCRIPT_SCHEMA)
    (tmp_path / ".knott/schemas/transcript.yaml").write_text(DOD_TRANSCRIPT_SCHEMA)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/foo.md").write_text(
        "---\ntype: script\ntitle: Episode 42\n---\n# Episode 42\n"
    )
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "transcripts/foo.md").write_text(
        "---\ntype: transcript\ntitle: Episode 42 transcript\n"
        'derived_from: "[Episode 42](../scripts/foo.md)"\n---\n# Transcript\n'
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_definition_of_done_markdown_link(dod_vault: Path) -> None:
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0
    assert result.output == SUCCESS


def test_definition_of_done_plain_path(dod_vault: Path) -> None:
    path = dod_vault / "transcripts/foo.md"
    path.write_text(
        path.read_text().replace('"[Episode 42](../scripts/foo.md)"', "../scripts/foo.md")
    )
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0
    assert result.output == SUCCESS


def test_definition_of_done_type_mismatch(dod_vault: Path) -> None:
    (dod_vault / ".knott/schemas/feedback.yaml").write_text("type: feedback\n")
    script = dod_vault / "scripts/foo.md"
    script.write_text(script.read_text().replace("type: script", "type: feedback"))
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert result.output == (
        "✗ transcripts/foo.md:4  derived_from\n"
        "  relation `derived_from` expects target type `script`\n"
        "  but `../scripts/foo.md` has type `feedback`\n"
        "\n"
        "1 validation error\n"
    )


def test_validate_from_subdirectory_walks_up(
    dod_vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(dod_vault / "transcripts")
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0, result.output


def test_issue_without_line_or_field_and_plural_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(fixture_path("missing-required-field"))
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 1
    assert "✗ scripts/untitled.md  title\n" in result.output
    assert result.output.endswith("\n\n2 validation errors\n")


def test_scoped_validate_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("relation-list"))
    result = runner.invoke(app, ["validate", "compilations/best-of.md"])
    assert result.exit_code == 0, result.output
    assert result.output == "✓ 3 schemas\n✓ 1 entity\n✓ 3 relations\n✓ vault is valid\n"


def test_scoped_validate_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("relation-list"))
    result = runner.invoke(app, ["validate", "scripts"])
    assert result.exit_code == 0, result.output
    assert "✓ 2 entities\n✓ 0 relations\n" in result.output
    result = runner.invoke(app, ["validate", "compilations"])
    assert result.exit_code == 1
    assert "2 validation errors" in result.output


def test_scoped_validate_still_checks_all_schemas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("unknown-relation-target-type"))
    result = runner.invoke(app, ["validate", "scripts/episode-42.md"])
    assert result.exit_code == 1
    assert "schemas/review.yaml" in result.output


def test_scoped_validate_not_an_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("valid-vault"))
    result = runner.invoke(app, ["validate", "notes/plain-note.md", "notes/readme.txt"])
    assert result.exit_code == 1
    assert "✗ notes/plain-note.md\n  not a Knott entity" in result.output
    assert "✗ notes/readme.txt\n" in result.output


def test_nonexistent_path_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("valid-vault"))
    result = runner.invoke(app, ["validate", "nope.md"])
    assert result.exit_code == 2


def test_no_vault_is_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["validate"]).exit_code == 2
    assert runner.invoke(app, ["types"]).exit_code == 2


@pytest.mark.parametrize("content", ["knott_version: [\n", "- a list\n"])
def test_malformed_config_is_usage_error(
    copy_fixture: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    vault = copy_fixture("valid-vault")
    (vault / ".knott/config.yaml").write_text(content)
    monkeypatch.chdir(vault)
    assert runner.invoke(app, ["validate"]).exit_code == 2


def test_missing_config_is_fine(
    copy_fixture: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = copy_fixture("valid-vault")
    (vault / ".knott/config.yaml").unlink()
    monkeypatch.chdir(vault)
    assert runner.invoke(app, ["validate"]).exit_code == 0


def test_validate_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("wrong-relation-target-type"))
    result = runner.invoke(app, ["validate", "--format", "json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["stats"] == {"schemas": 3, "entities": 3, "relations": 0}
    assert payload["issues"] == [
        {
            "code": "relation-target-type-mismatch",
            "path": "transcripts/foo.md",
            "line": 4,
            "field": "derived_from",
            "message": "relation `derived_from` expects target type `script`\n"
            "but `../scripts/foo.md` has type `feedback`",
        }
    ]


def test_types(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("valid-vault"))
    result = runner.invoke(app, ["types"])
    assert result.exit_code == 0
    assert result.output == "feedback\nscript\ntranscript\n"


def test_types_verbose(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("valid-vault"))
    result = runner.invoke(app, ["types", "--verbose"])
    assert result.exit_code == 0
    assert "transcript  (.knott/schemas/podcast/transcript.yaml)\n" in result.output
    assert "  Transcript of recorded spoken content.\n" in result.output


def test_types_with_schema_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(fixture_path("duplicate-schema-type"))
    result = runner.invoke(app, ["types"])
    assert result.exit_code == 1
    assert result.stdout == "script\ntranscript\n"
    assert "schema-duplicate-type" not in result.stdout
    assert "defined twice" in result.stderr


def test_init_creates_vault(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".knott/schemas").is_dir()
    assert (tmp_path / ".knott/config.yaml").read_text() == f"knott_version: {version()}\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == [".knott"]


def test_init_existing_vault_changes_nothing(tmp_path: Path) -> None:
    (tmp_path / ".knott").mkdir()
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert "already initialized" in result.output
    assert list((tmp_path / ".knott").iterdir()) == []


def test_init_defaults_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert (tmp_path / ".knott/config.yaml").exists()


def test_init_missing_directory_is_usage_error(tmp_path: Path) -> None:
    assert runner.invoke(app, ["init", str(tmp_path / "missing")]).exit_code == 2


def test_validate_and_types_write_nothing(
    copy_fixture: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = copy_fixture("valid-vault")
    before = sorted((p, p.stat().st_mtime_ns) for p in vault.rglob("*"))
    monkeypatch.chdir(vault)
    runner.invoke(app, ["validate"])
    runner.invoke(app, ["types"])
    assert sorted((p, p.stat().st_mtime_ns) for p in vault.rglob("*")) == before


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output == f"{version()}\n"
    assert version() == "0.1.0"


def test_config_with_invalid_characters_is_usage_error(
    copy_fixture: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = copy_fixture("valid-vault")
    (vault / ".knott/config.yaml").write_bytes(b"knott_version: \x00\n")
    monkeypatch.chdir(vault)
    assert runner.invoke(app, ["validate"]).exit_code == 2
