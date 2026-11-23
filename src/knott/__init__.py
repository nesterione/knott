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
    EntityRef,
    FixedEntity,
    InitResult,
    Issue,
    MigrateResult,
    Ontology,
    OntologyAttribute,
    OntologyType,
    Ref,
    RefGroup,
    Refs,
    SchemaInfo,
    Stats,
    ValidationResult,
)

__all__ = [
    "ConfigError",
    "EntityRef",
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
    "Ref",
    "RefGroup",
    "Refs",
    "SchemaInfo",
    "Stats",
    "ValidationResult",
    "VaultNotFoundError",
    "version",
]
