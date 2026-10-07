from __future__ import annotations

from pathlib import Path

import pytest

from knott import Knott, PathNotFoundError, PathOutsideVaultError, VaultNotFoundError

from .conftest import fixture_path


def test_open_walks_up_to_vault_root() -> None:
    vault = Knott.open(fixture_path("valid-vault") / "scripts" / "episode-42.md")
    assert vault.root == fixture_path("valid-vault").resolve()


def test_open_without_vault_raises(tmp_path: Path) -> None:
    with pytest.raises(VaultNotFoundError):
        Knott.open(tmp_path)


def test_validate_paths_relative_to_vault_root() -> None:
    vault = Knott.open(fixture_path("wrong-relation-target-type"))
    assert not vault.validate(["transcripts/foo.md"]).ok
    assert vault.validate(["scripts"]).ok


def test_validate_bad_paths_raise() -> None:
    vault = Knott.open(fixture_path("valid-vault"))
    with pytest.raises(PathNotFoundError):
        vault.validate(["missing.md"])
    with pytest.raises(PathOutsideVaultError):
        vault.validate([fixture_path("unknown-type")])


def test_results_are_plain_frozen_data() -> None:
    result = Knott.open(fixture_path("unknown-type")).validate()
    issue = result.issues[0]
    assert issue.model_dump() == {
        "code": "entity-unknown-type",
        "path": "notes/mystery.md",
        "line": 2,
        "field": "type",
        "message": issue.message,
    }
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError on frozen model
        issue.code = "x"


def test_docs_folder_is_a_valid_vault() -> None:
    """docs/ is written as a Knott vault; keep it valid."""
    docs = Path(__file__).parent.parent / "docs"
    result = Knott.open(docs).validate()
    assert result.ok, result.issues
    assert Knott.open(docs).types() == ["command", "concept", "decision", "guide", "issue_code"]
