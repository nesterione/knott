"""Public result types. All plain data."""

from __future__ import annotations

from collections.abc import Iterator

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


class OntologyAttribute(_Frozen):
    """An attribute declared by a type's schema, or a nested part of one."""

    name: str | None
    """Field name; None for a list's `items` or a map's `values`."""
    type: str
    """A scalar type name, or `list`, `object`, `map` or `reference`."""
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


class Ontology(_Frozen):
    """The vault's types and the references between them."""

    vault: str
    """Directory name of the vault root."""
    types: list[OntologyType]
    schema_issues: int
