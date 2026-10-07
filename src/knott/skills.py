"""Install the Agent Skill bundled with Knott into a project directory."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath

from knott.errors import KnottError

SKILL_NAME = "knott"


class SkillTarget(StrEnum):
    """Where agents look for project skills."""

    CLAUDE = "claude"
    AGENTS = "agents"

    @property
    def skills_dir(self) -> PurePosixPath:
        return PurePosixPath(f".{self.value}/skills")


class InstallStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class InstallResult:
    target: SkillTarget
    path: Path
    status: InstallStatus


def target_dir(root: Path, target: SkillTarget, skill: str = SKILL_NAME) -> Path:
    """Return the destination directory of ``skill`` for ``target`` under ``root``."""
    return root / target.skills_dir / skill


def _bundled(skill: str) -> Traversable:
    return files("knott") / "_skills" / skill


def _walk(node: Traversable, prefix: PurePosixPath) -> Iterator[tuple[PurePosixPath, bytes]]:
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        relative = prefix / child.name
        if child.is_dir():
            yield from _walk(child, relative)
        elif child.is_file():
            yield relative, child.read_bytes()


def bundled_files(skill: str = SKILL_NAME) -> dict[PurePosixPath, bytes]:
    """Return the bundled skill's files keyed by path relative to the skill directory."""
    return dict(_walk(_bundled(skill), PurePosixPath()))


def install_skill(root: Path, target: SkillTarget, *, force: bool = False) -> InstallResult:
    """Copy the bundled skill into ``root`` for ``target``.

    Files already present with identical bytes are left alone, files that differ are
    overwritten only with ``force``, and extra files at the destination are never touched.
    """
    destination = target_dir(root, target)
    if destination.exists() and not destination.is_dir():
        raise KnottError(f"{destination} exists and is not a directory")
    bundle = bundled_files()
    changed = {
        relative: content
        for relative, content in bundle.items()
        if not _same(destination / relative, content)
    }
    if not changed:
        return InstallResult(target, destination, InstallStatus.UNCHANGED)
    existed = any((destination / relative).exists() for relative in bundle)
    overwrites = any((destination / relative).exists() for relative in changed)
    if overwrites and not force:
        return InstallResult(target, destination, InstallStatus.CONFLICT)
    try:
        for relative, content in changed.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    except OSError as error:
        raise KnottError(f"cannot write {destination}: {error.strerror or error}") from error
    status = InstallStatus.UPDATED if existed else InstallStatus.CREATED
    return InstallResult(target, destination, status)


def _same(path: Path, content: bytes) -> bool:
    try:
        return path.is_file() and path.read_bytes() == content
    except OSError:
        return False
