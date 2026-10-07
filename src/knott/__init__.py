"""Knott: a local, file-first knowledge layer for AI agents."""

from knott.api import Knott, version
from knott.errors import (
    ConfigError,
    KnottError,
    PathNotFoundError,
    PathOutsideVaultError,
    VaultNotFoundError,
)
from knott.models import InitResult, Issue, SchemaInfo, Stats, ValidationResult

__all__ = [
    "ConfigError",
    "InitResult",
    "Issue",
    "Knott",
    "KnottError",
    "PathNotFoundError",
    "PathOutsideVaultError",
    "SchemaInfo",
    "Stats",
    "ValidationResult",
    "VaultNotFoundError",
    "version",
]
