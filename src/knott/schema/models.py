"""Internal schema definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ScalarType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


@dataclass(frozen=True)
class AttributeDef:
    name: str
    type: ScalarType
    required: bool = False
    description: str | None = None


@dataclass(frozen=True)
class RelationDef:
    name: str
    target: str
    required: bool = False
    description: str | None = None
    line: int | None = None
    """1-based line of the relation key in the schema file."""


@dataclass
class Schema:
    type: str
    path: str
    description: str | None = None
    attributes: dict[str, AttributeDef] = field(default_factory=dict)
    relations: dict[str, RelationDef] = field(default_factory=dict)
    unknown_relations: dict[str, RelationDef] = field(default_factory=dict)
    """Relations whose target type no schema defines. Kept for display, ignored by validation."""
