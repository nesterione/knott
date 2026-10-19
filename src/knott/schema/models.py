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
class ListShape:
    items: AttributeDef


@dataclass(frozen=True)
class ObjectShape:
    fields: dict[str, AttributeDef]
    """Declared fields in schema order. Undeclared keys are rejected."""


@dataclass(frozen=True)
class MapShape:
    values: AttributeDef
    """Free string keys; every value has this definition."""


Shape = ScalarType | ListShape | ObjectShape | MapShape

COMPOUND_KINDS = ("list", "object", "map")


def shape_kind(shape: Shape) -> str:
    """The `type` keyword of a shape: a scalar type name, or list / object / map."""
    if isinstance(shape, ListShape):
        return "list"
    if isinstance(shape, ObjectShape):
        return "object"
    if isinstance(shape, MapShape):
        return "map"
    return shape.value


def notation(shape: Shape) -> str:
    """Compact human form, e.g. ``list of object`` or ``map of map of string``."""
    if isinstance(shape, ListShape):
        return f"list of {notation(shape.items.shape)}"
    if isinstance(shape, MapShape):
        return f"map of {notation(shape.values.shape)}"
    return shape_kind(shape)


@dataclass(frozen=True)
class AttributeDef:
    name: str | None
    """Field name; None for a list's `items` or a map's `values`."""
    shape: Shape
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
