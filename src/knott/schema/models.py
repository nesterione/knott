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
    relation: str | None = None
    """The relation this reference names (spec 0006); None when it names none or an
    undefined one."""


@dataclass(frozen=True)
class FileShape:
    """A file that is not treated as an entity: a vault path or a connector URI (spec 0008)."""

    accept: tuple[str, ...] = ()
    """Lowercase extensions a vault file may have, without the dot. Empty: any."""


@dataclass(frozen=True)
class EnumShape:
    """A string that must be one of the listed options (spec 0009)."""

    options: tuple[tuple[str, str | None], ...]
    """``(option, description)`` pairs in the concept's order; never empty."""

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.options)


Shape = ScalarType | ListShape | ObjectShape | MapShape | ReferenceShape | FileShape | EnumShape

COMPOUND_KINDS = ("list", "object", "map")
REFERENCE_KIND = "reference"
FILE_KIND = "file"
ENUM_KIND = "enum"


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
    if isinstance(shape, FileShape):
        return FILE_KIND
    if isinstance(shape, EnumShape):
        return ENUM_KIND
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


@dataclass(frozen=True)
class RelationDef:
    """A relation file in ``.knott/relations/`` (spec 0006)."""

    name: str
    description: str | None
    inverse: str | None
    """The relation's name read from the target side."""
    symmetric: bool
    acyclic: bool
    guidance: str | None
    """The relation file's body, verbatim; None when it is blank."""
    path: str
    """Vault-relative path of the relation file."""
    lines: dict[str, int | None] = field(default_factory=dict, compare=False)
    """1-based line of each top-level key of the relation file."""


@dataclass(frozen=True)
class ConnectorDef:
    """A connector file in ``.knott/connectors/`` (spec 0008): a URI scheme the vault allows."""

    name: str
    """The URI scheme, lowercase."""
    description: str | None
    guidance: str | None
    """The connector file's body, verbatim; None when it is blank."""
    path: str
    """Vault-relative path of the connector file."""
    lines: dict[str, int | None] = field(default_factory=dict, compare=False)
    """1-based line of each top-level key of the connector file."""


@dataclass(frozen=True)
class LoopNeedDef:
    """One thing a loop stage needs (spec 0010): a property that is set, or an entity
    of ``type`` that points here through ``relation``."""

    kind: str
    """``property`` or ``inverse``."""
    property: str | None = None
    inverse: str | None = None
    """The relation's inverse, as written in the loop file."""
    relation: str | None = None
    type: str | None = None


@dataclass(frozen=True)
class LoopStageDef:
    name: str
    needs: tuple[LoopNeedDef, ...] = ()
    guidance: str | None = None


@dataclass(frozen=True)
class LoopDef:
    """A loop file in ``.knott/loops/`` (spec 0010)."""

    name: str
    description: str | None
    type: str
    property: str
    """A top-level enum property of ``type``; its value is the entity's stage."""
    stages: tuple[LoopStageDef, ...]
    """The path, in the loop's order."""
    exits: tuple[LoopStageDef, ...]
    """Options of the enum the loop leaves out, in the enum's order."""
    guidance: str | None
    """The body before the first stage heading; None when blank."""
    path: str
    lines: dict[str, int | None] = field(default_factory=dict, compare=False)


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
