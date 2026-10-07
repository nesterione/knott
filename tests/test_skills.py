from __future__ import annotations

from importlib.resources import files
from pathlib import Path, PurePosixPath

import pytest

from knott.errors import KnottError
from knott.skills import (
    InstallStatus,
    SkillTarget,
    bundled_files,
    install_skill,
    target_dir,
)

SKILL_MD = PurePosixPath("SKILL.md")


def test_skill_is_bundled_in_package() -> None:
    skill_md = files("knott") / "_skills" / "knott" / "SKILL.md"
    assert skill_md.is_file()
    assert skill_md.read_text(encoding="utf-8").startswith("---\nname: knott\n")


def test_bundled_files_include_skill_md() -> None:
    assert SKILL_MD in bundled_files()


@pytest.mark.parametrize(
    ("target", "expected"),
    [(SkillTarget.CLAUDE, ".claude/skills/knott"), (SkillTarget.AGENTS, ".agents/skills/knott")],
)
def test_target_dir(tmp_path: Path, target: SkillTarget, expected: str) -> None:
    assert target_dir(tmp_path, target) == tmp_path / expected


def test_install_creates_then_is_unchanged(tmp_path: Path) -> None:
    first = install_skill(tmp_path, SkillTarget.CLAUDE)
    assert first.status is InstallStatus.CREATED
    assert first.path == tmp_path / ".claude/skills/knott"
    assert (first.path / "SKILL.md").read_bytes() == bundled_files()[SKILL_MD]
    assert install_skill(tmp_path, SkillTarget.CLAUDE).status is InstallStatus.UNCHANGED


def test_install_conflict_leaves_file_untouched(tmp_path: Path) -> None:
    skill_md = target_dir(tmp_path, SkillTarget.AGENTS) / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("local edits\n")
    result = install_skill(tmp_path, SkillTarget.AGENTS)
    assert result.status is InstallStatus.CONFLICT
    assert skill_md.read_text() == "local edits\n"


def test_install_force_overwrites(tmp_path: Path) -> None:
    skill_md = target_dir(tmp_path, SkillTarget.CLAUDE) / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("local edits\n")
    result = install_skill(tmp_path, SkillTarget.CLAUDE, force=True)
    assert result.status is InstallStatus.UPDATED
    assert skill_md.read_bytes() == bundled_files()[SKILL_MD]


def test_install_preserves_extra_files(tmp_path: Path) -> None:
    extra = target_dir(tmp_path, SkillTarget.CLAUDE) / "notes.md"
    extra.parent.mkdir(parents=True)
    extra.write_text("mine\n")
    assert install_skill(tmp_path, SkillTarget.CLAUDE).status is InstallStatus.CREATED
    assert extra.read_text() == "mine\n"


def test_install_into_file_raises(tmp_path: Path) -> None:
    destination = target_dir(tmp_path, SkillTarget.CLAUDE)
    destination.parent.mkdir(parents=True)
    destination.write_text("not a directory\n")
    with pytest.raises(KnottError, match="not a directory"):
        install_skill(tmp_path, SkillTarget.CLAUDE)


def test_install_unwritable_raises(tmp_path: Path) -> None:
    (tmp_path / ".claude").write_text("blocks the skills directory\n")
    with pytest.raises(KnottError, match="cannot write"):
        install_skill(tmp_path, SkillTarget.CLAUDE)
