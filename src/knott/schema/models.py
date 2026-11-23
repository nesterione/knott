"""Internal schema definitions."""

from __future__ import annotations

from collections.abc import Iterator
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


@dataclass(frozen=True)
class ReferenceShape:
    """A reference to one entity whose type is one of ``targets`` (decision 0010)."""

    targets: tuple[str, ...]
    """Target types that some concept defines, in schema order."""
    unknown: tuple[str, ...] = ()
    """Target types no concept defines. Kept for display; never enforced."""


Shape = ScalarType | ListShape | ObjectShape | MapShape | ReferenceShape

COMPOUND_KINDS = ("list", "object", "map")
REFERENCE_KIND = "reference"


def shape_kind(shape: Shape) -> str:
    """The `type` keyword of a shape: a scalar type name, or list / object / map."""
    if isinstance(shape, ListShape):
        return "list"
    if isinstance(shape, ObjectShape):
        return "object"
    if isinstance(shape, MapShape):
        return "map"
    if isinstance(shape, ReferenceShape):
        return REFERENCE_KIND
    return shape.value


def notation(shape: Shape) -> str:
    """Compact human form, e.g. ``list of object`` or ``list of reference → a | b``."""
    if isinstance(shape, ListShape):
        return f"list of {notation(shape.items.shape)}"
    if isinstance(shape, MapShape):
        return f"map of {notation(shape.values.shape)}"
    if isinstance(shape, ReferenceShape) and shape.targets:
        return f"{REFERENCE_KIND} → {' | '.join(shape.targets)}"
    return shape_kind(shape)


@dataclass(frozen=True)
class AttributeDef:
    name: str | None
    """Field name; None for a list's `items` or a map's `values`."""
    shape: Shape
    required: bool = False
    description: str | None = None


@dataclass
class Schema:
    type: str
    """The concept's `name`: the `type` its entities declare."""
    path: str
    """Vault-relative path of the concept file."""
    description: str | None = None
    kid_required: bool = False
    """Set by `kid: required`: every entity of this type must have a `kid`."""
    properties: dict[str, AttributeDef] = field(default_factory=dict)
    """Top-level properties in schema order; references are properties too."""
    template: str | None = None
    """The concept file's body, verbatim; None when it is blank."""


SchemaPath = tuple[str, ...]
"""Key path inside ``properties``, e.g. ``("speakers", "items", "fields", "person")``."""


def iter_references(schema: Schema) -> Iterator[tuple[SchemaPath, ReferenceShape]]:
    """Every reference shape in ``schema``, at any depth, in schema order."""
    for name, definition in schema.properties.items():
        yield from _references(definition, (name,))


def _references(
    definition: AttributeDef, path: SchemaPath
) -> Iterator[tuple[SchemaPath, ReferenceShape]]:
    shape = definition.shape
    if isinstance(shape, ReferenceShape):
        yield path, shape
    elif isinstance(shape, ListShape):
        yield from _references(shape.items, (*path, "items"))
    elif isinstance(shape, MapShape):
        yield from _references(shape.values, (*path, "values"))
    elif isinstance(shape, ObjectShape):
        for name, field_def in shape.fields.items():
            yield from _references(field_def, (*path, "fields", name))
