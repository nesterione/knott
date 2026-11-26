"""Exceptions for conditions that stop a run (CLI exit code 2).

Validation problems are never raised; they are returned as ``Issue`` data.
"""

from __future__ import annotations


class KnottError(Exception):
    """Base class for usage and configuration errors."""


class VaultNotFoundError(KnottError):
    """No directory containing ``.knott/`` was found."""


class ConfigError(KnottError):
    """``.knott/config.yaml`` is unreadable or malformed."""


class PathNotFoundError(KnottError):
    """A path argument does not exist."""


class PathOutsideVaultError(KnottError):
    """A path argument lies outside the vault root."""


class MigrateError(KnottError):
    """A legacy ``.knott/schemas/`` file cannot be converted to a concept file."""


class MoveError(KnottError):
    """`Knott.move()` stopped on an I/O error after it started writing (spec 0018)."""

    def __init__(self, message: str, written: list[str]) -> None:
        super().__init__(message)
        self.written = written
        """Vault-relative paths of the files already written, in the order written."""
