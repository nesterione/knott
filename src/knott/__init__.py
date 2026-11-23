"""Knott: a local, file-first knowledge layer for AI agents."""

from knott.api import Knott, version
from knott.errors import (
    ConfigError,
    KnottError,
    MigrateError,
    PathNotFoundError,
    PathOutsideVaultError,
    VaultNotFoundError,
)
from knott.models import (
    FixedEntity,
    InitResult,
    Issue,
    MigrateResult,
    Ontology,
    OntologyAttribute,
    OntologyType,
    SchemaInfo,
    Stats,
    ValidationResult,
)

__all__ = [
    "ConfigError",
    "FixedEntity",
    "InitResult",
    "Issue",
    "Knott",
    "KnottError",
    "MigrateError",
    "MigrateResult",
    "Ontology",
    "OntologyAttribute",
    "OntologyType",
    "PathNotFoundError",
    "PathOutsideVaultError",
    "SchemaInfo",
    "Stats",
    "ValidationResult",
    "VaultNotFoundError",
    "version",
]
