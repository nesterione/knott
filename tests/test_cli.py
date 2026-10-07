from __future__ import annotations

import json
import os
import re
import stat
import tomllib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
import questionary
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

from knott import Knott, cli, version
from knott.cli import app
from knott.skills import SkillTarget

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


@pytest.fixture
def no_browser(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record webbrowser.open calls instead of launching a browser."""
    opened: list[str] = []

    def fake_open(url: str, *args: object, **kwargs: object) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr("webbrowser.open", fake_open)
    return opened


def test_view_writes_page(tmp_path: Path, no_browser: list[str]) -> None:
    out = tmp_path / "out.html"
    result = runner.invoke(
        app, ["view", str(fixture_path("valid-vault")), "--no-open", "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert result.stdout == f"Wrote {out}\n"
    assert result.stderr == ""
    page = out.read_text(encoding="utf-8")
    for name in ["feedback", "script", "transcript"]:
        assert f'"type": "{name}"' in page
    assert no_browser == []


def test_view_opens_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_browser: list[str]
) -> None:
    monkeypatch.chdir(fixture_path("valid-vault"))
    out = tmp_path / "out.html"
    result = runner.invoke(app, ["view", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert no_browser == [out.resolve().as_uri()]


def test_view_defaults_to_private_temp_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_browser: list[str]
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.chdir(fixture_path("valid-vault"))
    private = tmp_path / f"knott-{os.getuid()}"
    expected = private / "knott-ontology-valid-vault.html"
    result = runner.invoke(app, ["view", "--no-open"])
    assert result.exit_code == 0, result.output
    assert result.stdout == f"Wrote {expected}\n"
    assert stat.S_IMODE(private.stat().st_mode) == 0o700
    # The next run reuses the same file instead of piling up new ones.
    expected.write_text("stale", encoding="utf-8")
    result = runner.invoke(app, ["view", "--no-open"])
    assert result.exit_code == 0, result.output
    assert '"type": "script"' in expected.read_text(encoding="utf-8")
    assert sorted(p.name for p in tmp_path.iterdir()) == [private.name]


def test_view_refuses_symlinked_temp_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_browser: list[str]
) -> None:
    temp, elsewhere = tmp_path / "tmp", tmp_path / "elsewhere"
    temp.mkdir()
    elsewhere.mkdir(mode=0o700)
    (temp / f"knott-{os.getuid()}").symlink_to(elsewhere)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(temp))
    result = runner.invoke(app, ["view", str(fixture_path("valid-vault")), "--no-open"])
    assert result.exit_code == 2
    assert "error: cannot write" in result.stderr
    assert "is not a directory" in result.stderr
    assert list(elsewhere.iterdir()) == []


def test_view_refuses_shared_temp_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_browser: list[str]
) -> None:
    shared = tmp_path / f"knott-{os.getuid()}"
    shared.mkdir()
    shared.chmod(0o777)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    result = runner.invoke(app, ["view", str(fixture_path("valid-vault")), "--no-open"])
    assert result.exit_code == 2
    assert "is not private to the current user" in result.stderr
    assert list(shared.iterdir()) == []


def test_view_without_browser_prints_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("webbrowser.open", lambda url, *args, **kwargs: False)
    out = tmp_path / "out.html"
    result = runner.invoke(app, ["view", str(fixture_path("valid-vault")), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert result.stderr == f"could not open a browser; open {out}\n"
    assert out.is_file()


def test_view_empty_vault_is_usage_error(tmp_path: Path, no_browser: list[str]) -> None:
    (tmp_path / ".knott/schemas").mkdir(parents=True)
    result = runner.invoke(
        app, ["view", str(tmp_path), "--no-open", "-o", str(tmp_path / "o.html")]
    )
    assert result.exit_code == 2
    assert "error: no types to show (add schemas to .knott/schemas/)" in result.stderr
    assert not (tmp_path / "o.html").exists()


def test_view_with_schema_issues_still_writes_page(tmp_path: Path, no_browser: list[str]) -> None:
    out = tmp_path / "out.html"
    vault = fixture_path("duplicate-schema-type")
    result = runner.invoke(app, ["view", str(vault), "--no-open", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert result.stdout == f"Wrote {out}\n"
    assert "1 schema issue — run knott validate" in result.stderr
    assert '"type": "script"' in out.read_text(encoding="utf-8")


def test_view_reports_plural_schema_issues(tmp_path: Path, no_browser: list[str]) -> None:
    Knott.init(tmp_path)
    schemas = tmp_path / ".knott" / "schemas"
    (schemas / "a.yaml").write_text("type: a\nrelations:\n  x:\n    target: nope\n")
    (schemas / "b.yaml").write_text("type: b\nrelations:\n  y:\n    target: gone\n")
    out = tmp_path / "out.html"
    result = runner.invoke(app, ["view", str(tmp_path), "--no-open", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert result.stderr == "2 schema issues — run knott validate\n"


def test_view_nonexistent_path_is_usage_error(tmp_path: Path, no_browser: list[str]) -> None:
    result = runner.invoke(app, ["view", str(tmp_path / "nope"), "--no-open"])
    assert result.exit_code == 2
    assert "error: path does not exist" in result.stderr


def test_view_unwritable_output_is_usage_error(tmp_path: Path, no_browser: list[str]) -> None:
    out = tmp_path / "missing-dir" / "out.html"
    result = runner.invoke(app, ["view", str(fixture_path("valid-vault")), "-o", str(out)])
    assert result.exit_code == 2
    assert "error: cannot write" in result.stderr
    assert no_browser == []


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
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert version() == pyproject["project"]["version"]


def test_config_with_invalid_characters_is_usage_error(
    copy_fixture: Callable[[str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = copy_fixture("valid-vault")
    (vault / ".knott/config.yaml").write_bytes(b"knott_version: \x00\n")
    monkeypatch.chdir(vault)
    assert runner.invoke(app, ["validate"]).exit_code == 2


class FakePrompt:
    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.application = SimpleNamespace(key_bindings=None)

    def ask(self) -> object:
        return self.answer


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_is_interactive", lambda: False)
    return tmp_path


def _interactive(
    monkeypatch: pytest.MonkeyPatch, selected: list[SkillTarget] | None, overwrite: bool = False
) -> None:
    monkeypatch.setattr(cli, "_is_interactive", lambda: True)
    monkeypatch.setattr(questionary, "checkbox", lambda *a, **k: FakePrompt(selected))
    monkeypatch.setattr(questionary, "confirm", lambda *a, **k: FakePrompt(overwrite))


def _plain(output: str) -> str:
    """Strip ANSI styling; CI forces colored help output."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def test_help_advertises_skill() -> None:
    result = runner.invoke(app, ["--help"], env={"COLUMNS": "200"})
    assert "knott skill install" in _plain(result.output)


def test_help_lists_view() -> None:
    result = runner.invoke(app, ["--help"], env={"COLUMNS": "200"})
    assert re.search(r"\bview\b", _plain(result.output))


def test_skill_install_help_lists_targets() -> None:
    result = runner.invoke(app, ["skill", "install", "--help"], env={"COLUMNS": "200"})
    assert "--claude" in _plain(result.output)
    assert "--agents" in _plain(result.output)


@pytest.mark.parametrize(
    ("flags", "dirs"),
    [
        (["--claude"], [".claude/skills/knott"]),
        (["--agents"], [".agents/skills/knott"]),
        (["--claude", "--agents"], [".claude/skills/knott", ".agents/skills/knott"]),
    ],
)
def test_skill_install_flags(project: Path, flags: list[str], dirs: list[str]) -> None:
    result = runner.invoke(app, ["skill", "install", *flags])
    assert result.exit_code == 0, result.output
    assert result.output == "".join(f"✓ {d}  installed\n" for d in dirs)
    for d in dirs:
        assert (project / d / "SKILL.md").is_file()
    assert runner.invoke(app, ["skill", "install", *flags]).output == "".join(
        f"✓ {d}  up to date\n" for d in dirs
    )


def test_skill_install_into_path_argument(project: Path) -> None:
    (project / "sub").mkdir()
    result = runner.invoke(app, ["skill", "install", "sub", "--claude"])
    assert result.exit_code == 0, result.output
    assert (project / "sub/.claude/skills/knott/SKILL.md").is_file()


def test_skill_install_conflict_needs_force(project: Path) -> None:
    skill_md = project / ".claude/skills/knott/SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("local edits\n")
    result = runner.invoke(app, ["skill", "install", "--claude"])
    assert result.exit_code == 1
    assert "--force" in result.output
    assert skill_md.read_text() == "local edits\n"
    result = runner.invoke(app, ["skill", "install", "--claude", "--force"])
    assert result.exit_code == 0, result.output
    assert result.output == "✓ .claude/skills/knott  updated\n"


def test_skill_install_missing_path_is_usage_error(project: Path) -> None:
    result = runner.invoke(app, ["skill", "install", "missing", "--claude"])
    assert result.exit_code == 2


def test_skill_install_without_flags_or_tty_is_usage_error(project: Path) -> None:
    result = runner.invoke(app, ["skill", "install"])
    assert result.exit_code == 2
    assert "pass --claude and/or --agents" in result.output
    assert not (project / ".claude").exists()


def test_skill_install_interactive_selection(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _interactive(monkeypatch, [SkillTarget.AGENTS])
    result = runner.invoke(app, ["skill", "install"])
    assert result.exit_code == 0, result.output
    assert (project / ".agents/skills/knott/SKILL.md").is_file()
    assert not (project / ".claude").exists()


@pytest.mark.parametrize("selected", [None, []])
def test_skill_install_interactive_cancel(
    project: Path, monkeypatch: pytest.MonkeyPatch, selected: list[SkillTarget] | None
) -> None:
    _interactive(monkeypatch, selected)
    result = runner.invoke(app, ["skill", "install"])
    assert result.exit_code == 1
    assert result.output == "Nothing installed.\n"


@pytest.mark.parametrize(("overwrite", "exit_code"), [(True, 0), (False, 1)])
def test_skill_install_interactive_conflict_confirm(
    project: Path, monkeypatch: pytest.MonkeyPatch, overwrite: bool, exit_code: int
) -> None:
    skill_md = project / ".claude/skills/knott/SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("local edits\n")
    _interactive(monkeypatch, [SkillTarget.CLAUDE], overwrite=overwrite)
    result = runner.invoke(app, ["skill", "install"])
    assert result.exit_code == exit_code
    assert (skill_md.read_text() == "local edits\n") is not overwrite


@pytest.mark.parametrize(
    "make",
    [
        lambda **k: questionary.checkbox("Pick:", ["a", "b"], **k),
        lambda **k: questionary.confirm("Sure?", **k),
    ],
)
def test_ask_escape_cancels(make: Callable[..., questionary.Question]) -> None:
    with create_pipe_input() as pipe:
        pipe.send_text("\x1b")
        pipe.flush()
        assert cli._ask(make(input=pipe, output=DummyOutput())) is None
