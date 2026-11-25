"""Public result types. All plain data."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Issue(_Frozen):
    """One validation problem."""

    code: str
    path: str
    """Vault-relative POSIX path of the file with the problem."""
    line: int | None = None
    """1-based line number, when known."""
    field: str | None = None
    message: str


class Stats(_Frozen):
    schemas: int = 0
    entities: int = 0
    relations: int = 0


class FixedEntity(_Frozen):
    """An entity that `validate(fix=True)` gave a new `kid`."""

    path: str
    kid: str


class ValidationResult(_Frozen):
    issues: list[Issue]
    stats: Stats
    fixed: list[FixedEntity] = []
    """Entities that got a new `kid` (only with ``fix=True``)."""

    @property
    def ok(self) -> bool:
        return not self.issues


class SchemaInfo(_Frozen):
    """A discovered entity type."""

    type: str
    description: str | None
    path: str
    """Vault-relative path of the schema file."""


class InitResult(_Frozen):
    root: str
    created: bool


class MigrateResult(_Frozen):
    """What `Knott.migrate()` changed."""

    written: list[str]
    """Vault-relative paths of the concept files written, sorted."""
    removed: str
    """The legacy folder that was deleted (``.knott/schemas``)."""
    list_fields: list[str]
    """Relations converted to ``list`` of ``reference``, as ``<type>.<field>``."""


class EnumOption(_Frozen):
    """One allowed value of an `enum` property (spec 0009)."""

    value: str
    description: str | None = None


class OntologyAttribute(_Frozen):
    """An attribute declared by a type's schema, or a nested part of one."""

    name: str | None
    """Field name; None for a list's `items` or a map's `values`."""
    type: str
    """A scalar type name, or `list`, `object`, `map`, `reference`, `file` or `enum`."""
    required: bool
    description: str | None
    items: OntologyAttribute | None = None
    """For a `list`: the definition of each item."""
    values: OntologyAttribute | None = None
    """For a `map`: the definition of each value (keys are free strings)."""
    fields: list[OntologyAttribute] = []
    """For an `object`: its declared fields, in schema order."""
    targets: list[str] = []
    """For a `reference`: target types that some concept defines, in schema order."""
    unknown_targets: list[str] = []
    """For a `reference`: target types no concept defines (shown, never enforced)."""
    relation: str | None = None
    """For a `reference`: the relation it names, when a relation file defines it."""
    accept: list[str] = []
    """For a `file`: the extensions a vault file may have, without the dot. Empty: any."""
    options: list[EnumOption] = []
    """For an `enum`: the allowed values, in the concept's order."""

    @property
    def notation(self) -> str:
        """Compact form of the type, e.g. ``list of object`` or ``list of reference → a | b``."""
        inner = self.items or self.values
        if inner is not None:
            return f"{self.type} of {inner.notation}"
        if self.targets:
            return f"{self.type} → {' | '.join(self.targets)}"
        return self.type


class OntologyType(_Frozen):
    """A type in the ontology, with its fields and the number of entities using it."""

    type: str
    description: str | None
    path: str
    """Vault-relative path of the schema file."""
    count: int
    """Markdown files whose frontmatter `type` is this type."""
    kid_required: bool = False
    """The schema says `kid: required`."""
    properties: list[OntologyAttribute]
    """Top-level properties in schema order; references are properties too."""
    template: str | None = None
    """The concept file's body: a template for entity bodies. None when blank."""

    def references(self) -> list[tuple[str, OntologyAttribute]]:
        """Every reference property at any depth, in schema order, with its path.

        Paths use ``[]`` for a list's items and ``*`` for a map's values, e.g.
        ``derived_from``, ``sources[]``, ``speakers[].person``, ``roles.*``.
        """
        return [(path, node) for path, node, _ in iter_reference_paths(self.properties)]


def iter_reference_paths(
    properties: list[OntologyAttribute],
) -> Iterator[tuple[str, OntologyAttribute, bool]]:
    """Walk references like `OntologyType.references`, also yielding whether each is required.

    A reference is required when every named step on its path is required, so every
    valid entity holds at least one value there.
    """
    for prop in properties:
        yield from _walk_references(prop, prop.name or "", prop.required)


def _walk_references(
    node: OntologyAttribute, path: str, required: bool
) -> Iterator[tuple[str, OntologyAttribute, bool]]:
    if node.type == "reference":
        yield path, node, required
    elif node.items is not None:
        yield from _walk_references(node.items, f"{path}[]", required)
    elif node.values is not None:
        yield from _walk_references(node.values, f"{path}.*", required)
    for field in node.fields:
        yield from _walk_references(field, f"{path}.{field.name}", required and field.required)


class RelationDefinition(_Frozen):
    """A relation file in ``.knott/relations/`` (spec 0006)."""

    name: str
    description: str | None
    inverse: str | None
    """The relation's name read from the target side."""
    symmetric: bool
    acyclic: bool
    guidance: str | None
    """The relation file's body, verbatim; None when blank."""
    path: str
    """Vault-relative path of the relation file."""


class ConnectorDefinition(_Frozen):
    """A connector file in ``.knott/connectors/`` (spec 0008)."""

    name: str
    """The URI scheme of files kept behind this connector, lowercase."""
    description: str | None
    guidance: str | None
    """The connector file's body, verbatim; None when blank."""
    path: str
    """Vault-relative path of the connector file."""


LoopNeedKind = Literal["property", "inverse"]


class LoopNeed(_Frozen):
    """One thing a loop stage needs (spec 0010)."""

    kind: LoopNeedKind
    property: str | None = None
    """For ``property``: the top-level property that must be set."""
    inverse: str | None = None
    """For ``inverse``: the relation's inverse, e.g. ``materials``."""
    relation: str | None = None
    """For ``inverse``: the relation the pointing entity's reference names."""
    type: str | None = None
    """For ``inverse``: the type of the entity that must point here."""
    since: str
    """The stage that declares the need."""


class LoopStage(_Frozen):
    """A stage of a loop, or a side exit (which never has needs)."""

    name: str
    needs: list[LoopNeed] = []
    guidance: str | None = None
    """The part of the loop file's body under ``## <name>``; None when blank."""


class LoopDefinition(_Frozen):
    """A loop file in ``.knott/loops/`` (spec 0010)."""

    name: str
    description: str | None
    type: str
    property: str
    """The top-level enum property of ``type`` whose value is an entity's stage."""
    stages: list[LoopStage]
    """The path, in the loop's order."""
    exits: list[LoopStage]
    """Options of the enum the loop leaves out, in the enum's order."""
    guidance: str | None
    """The body before the first stage heading; None when blank."""
    path: str
    """Vault-relative path of the loop file."""


class LoopEntity(_Frozen):
    """An entity in a loop."""

    path: str
    kid: str | None
    title: str
    """The entity's `title` when its type has that string property and it is set,
    else the file name."""
    unmet: list[LoopNeed] = []
    """Needs of its stage, or an earlier one, that are not met: `loop-stage-unmet`."""
    next: str | None = None
    """The following stage on the path; None at the last stage, a side exit or no stage."""
    missing_next: list[LoopNeed] = []
    """Needs of ``next`` that are not met yet. Not issues."""


class LoopPlacement(_Frozen):
    stage: str
    entities: list[LoopEntity]


class LoopReport(_Frozen):
    """Where every entity of a loop's type stands (spec 0010)."""

    loop: LoopDefinition
    stages: list[LoopPlacement]
    """One per stage on the path, in order, empty stages included."""
    exits: list[LoopPlacement]
    unplaced: list[LoopEntity]
    """Entities whose stage property is absent or not an option."""


class Ontology(_Frozen):
    """The vault's types, relations and the references between them."""

    vault: str
    """Directory name of the vault root."""
    types: list[OntologyType]
    schema_issues: int
    relations: list[RelationDefinition] = []
    """Every relation that loaded, sorted by name."""
    connectors: list[ConnectorDefinition] = []
    """Every connector that loaded, sorted by name."""
    loops: list[LoopDefinition] = []
    """Every loop that loaded, sorted by name."""


RefKind = Literal["inverse", "symmetric", "relation", "property"]
RefDirection = Literal["in", "out", "both"]


class EntityRef(_Frozen):
    """The entity whose references `Knott.refs()` lists."""

    path: str
    """Vault-relative POSIX path."""
    type: str
    """The frontmatter `type`, as written."""
    kid: str | None
    """The entity's `kid`, when it has a valid one."""


class Ref(_Frozen):
    """One linked entity in a reverse-lookup group."""

    path: str
    """Vault-relative path of the linked entity."""
    type: str
    """The linked entity's frontmatter `type`."""
    kid: str | None
    """The linked entity's `kid`, when it has a valid one."""
    field: str
    """Where the link is stored, e.g. ``affects[0]``: in the linked entity, or, for
    direction ``out``, in the looked-up entity."""
    line: int | None
    """1-based line of that reference, in the file that stores it."""
    direction: RefDirection
    """``in`` (the linked entity stores it), ``out`` (only the looked-up entity stores
    it) or ``both``. Always ``in`` outside symmetric groups."""


class RefGroup(_Frozen):
    """References that share a label: an inverse name, a relation, or a property."""

    label: str
    """``superseded_by``, ``related``, ``← about`` or ``← guide.concepts[]``."""
    kind: RefKind
    relation: str | None
    """The relation the referring properties name; None for ``property`` groups."""
    references: list[Ref]


class Refs(_Frozen):
    """Every reference in the vault that resolves to one entity (spec 0006)."""

    entity: EntityRef
    groups: list[RefGroup]
    """``inverse``, ``symmetric`` and ``relation`` groups by label, then ``property``
    groups by label."""
