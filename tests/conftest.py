from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from knott import Knott, ValidationResult

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES / name


def validate_fixture(name: str, paths: list[str] | None = None) -> ValidationResult:
    return Knott.open(fixture_path(name)).validate(paths)


def triples(result: ValidationResult) -> list[tuple[str, int | None, str]]:
    return [(i.path, i.line, i.code) for i in result.issues]


@pytest.fixture
def copy_fixture(tmp_path: Path) -> Callable[[str], Path]:
    """Copy a fixture vault into tmp_path so a test can modify it."""

    def _copy(name: str) -> Path:
        target = tmp_path / name
        shutil.copytree(fixture_path(name), target)
        return target

    return _copy
