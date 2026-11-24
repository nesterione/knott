"""One run's view of the vault files, and the index of every resolved reference.

``VaultSession`` caches parsed files and the `kid` index for one run. Its
``references()`` index is built on first use, once, and shared by everything that
needs the vault's reference graph: cycle checks of acyclic relations and reverse
lookup (spec 0006). Resolution is ``resolve_reference``, the same as validation;
the session memoizes each resolution and each directory listing, so validation and
the index resolve a reference once and a run lists each directory once.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knott._yaml import KeyPath
from knott.schema.models import (
    AttributeDef,
    ListShape,
    MapShape,
    ObjectShape,
    ReferenceShape,
    Schema,
)
from knott.schema.validator import format_field_path
from knott.vault.discovery import iter_markdown
from knott.vault.entity import MarkdownFile, read_markdown
from knott.vault.files import ResolvedFile, resolve_file
from knott.vault.kid import KidIndex, build_index
from knott.vault.links import LinkError, ResolvedReference, list_dir_entries, resolve_reference


@dataclass(frozen=True)
class IndexedReference:
    """One reference in an entity's frontmatter that resolves to an entity."""

    source: str
    """Vault-relative path of the entity that holds the reference."""
    source_type: str
    key_path: KeyPath
    """Where the value sits in the source's frontmatter, e.g. ``("history", 2, "replaces")``."""
    field: str
    """``key_path`` as written in issues: ``history[2].replaces``."""
    property_path: str
    """The declaring property in ``OntologyType.references()`` notation:
    ``history[].replaces``, ``roles.*``."""
    line: int | None
    """1-based line of the reference in the source file."""
    relation: str | None
    """The relation the declaring property names, if it names a defined one."""
    target: str
    """Vault-relative path of the referenced entity."""
    target_type: Any
    """The referenced entity's frontmatter `type`, as written."""
    type_ok: bool
    """The target passes the property's target-type check."""


class ReferenceIndex:
    """Every resolved reference of the vault's entities, with lookups by both ends.

    Only declared reference properties count. A reference is indexed when it resolves
    to a Markdown file that is an entity with valid frontmatter, whether or not the
    target-type check passes (see ``IndexedReference.type_ok``). Entities with invalid
    frontmatter or an unknown type hold no indexed references.
    """

    def __init__(self, references: list[IndexedReference]) -> None:
        self.references: tuple[IndexedReference, ...] = tuple(references)
        """In source path order, then in schema order within a source."""
        self._by_target: dict[str, list[IndexedReference]] = {}
        self._by_source: dict[str, list[IndexedReference]] = {}
        self._by_relation: dict[str, list[IndexedReference]] = {}
        for ref in self.references:
            self._by_target.setdefault(ref.target, []).append(ref)
            self._by_source.setdefault(ref.source, []).append(ref)
            if ref.relation is not None:
                self._by_relation.setdefault(ref.relation, []).append(ref)

    def to(self, target: str) -> list[IndexedReference]:
        """References that resolve to ``target`` (a vault-relative path)."""
        return list(self._by_target.get(target, ()))

    def from_(self, source: str) -> list[IndexedReference]:
        """References held by ``source`` (a vault-relative path)."""
        return list(self._by_source.get(source, ()))

    def with_relation(self, name: str) -> list[IndexedReference]:
        """References at properties that name the relation ``name``."""
        return list(self._by_relation.get(name, ()))


class VaultSession:
    """Parsed files, the `kid` index and the reference index for one run.

    Everything is computed on first use and kept, so a run that never touches a
    `kid` or the reference graph pays nothing for them. Nothing outlives the session.
    """

    def __init__(
        self, root: Path, schemas: dict[str, Schema], connectors: Collection[str] = ()
    ) -> None:
        self.root = root
        self.schemas = schemas
        self.connectors = frozenset(connectors)
        """Names of the declared connectors (spec 0008)."""
        self._files: dict[str, MarkdownFile] = {}
        self._all_markdown: list[str] | None = None
        self._kids: KidIndex | None = None
        self._references: ReferenceIndex | None = None
        self._listings: dict[Path, frozenset[str] | None] = {}
        self._resolved: dict[tuple[str, str], ResolvedReference | LinkError] = {}

    @property
    def all_markdown(self) -> list[str]:
        """Vault-relative paths of every Markdown file, sorted."""
        if self._all_markdown is None:
            self._all_markdown = iter_markdown(self.root)
        return self._all_markdown

    def lookup(self, rel_path: str) -> MarkdownFile:
        parsed = self._files.get(rel_path)
        if parsed is None:
            parsed = read_markdown(self.root / rel_path, rel_path)
            self._files[rel_path] = parsed
        return parsed

    def kids(self) -> KidIndex:
        if self._kids is None:
            self._kids = build_index(self.all_markdown, self.lookup)
        return self._kids

    def resolve(self, source: str, reference: str) -> ResolvedReference:
        """Resolve a reference held by ``source``; raises ``LinkError``.

        Memoized per ``(source, reference)``, failures included."""
        key = (source, reference)
        outcome = self._resolved.get(key)
        if outcome is None:
            try:
                outcome = resolve_reference(self.root, source, reference, self.kids, self.list_dir)
            except LinkError as error:
                outcome = error
            self._resolved[key] = outcome
        if isinstance(outcome, LinkError):
            raise LinkError(outcome.code, outcome.message)
        return outcome

    def resolve_file(self, source: str, value: str, accept: tuple[str, ...] = ()) -> ResolvedFile:
        """Resolve a file value held by ``source`` (spec 0008); raises ``LinkError``."""
        return resolve_file(self.root, source, value, self.connectors, accept, self.list_dir)

    def list_dir(self, directory: Path) -> frozenset[str] | None:
        """``directory``'s entry names (``None`` if unlistable), listed once per session."""
        if directory not in self._listings:
            self._listings[directory] = list_dir_entries(directory)
        return self._listings[directory]

    def references(self) -> ReferenceIndex:
        """The vault's reference index, built on the first call."""
        if self._references is None:
            found: list[IndexedReference] = []
            for rel_path in self.all_markdown:
                found.extend(self._entity_references(rel_path))
            self._references = ReferenceIndex(found)
        return self._references

    def _entity_references(self, rel_path: str) -> Iterator[IndexedReference]:
        entity = self.lookup(rel_path)
        if entity.error is not None or not entity.is_entity:
            return
        source_type = entity.type
        schema = self.schemas.get(source_type) if isinstance(source_type, str) else None
        if schema is None:
            return
        assert entity.frontmatter is not None
        for name, definition in schema.properties.items():
            values = _reference_values(definition, (name,), name, entity.frontmatter.get(name))
            for key_path, property_path, shape, value in values:
                indexed = self._index_one(entity, schema, key_path, property_path, shape, value)
                if indexed is not None:
                    yield indexed

    def _index_one(
        self,
        entity: MarkdownFile,
        schema: Schema,
        key_path: KeyPath,
        property_path: str,
        shape: ReferenceShape,
        value: str,
    ) -> IndexedReference | None:
        try:
            resolved = self.resolve(entity.path, value)
        except LinkError:
            return None
        target = self.lookup(resolved.target)
        if target.error is not None or not target.is_entity:
            return None
        return IndexedReference(
            source=entity.path,
            source_type=schema.type,
            key_path=key_path,
            field=format_field_path(key_path),
            property_path=property_path,
            line=entity.line_of(key_path),
            relation=shape.relation,
            target=resolved.target,
            target_type=target.type,
            type_ok=not shape.targets or target.type in shape.targets,
        )


def _reference_values(
    definition: AttributeDef, key_path: KeyPath, property_path: str, value: Any
) -> Iterator[tuple[KeyPath, str, ReferenceShape, str]]:
    """Reference strings in ``value``, walked along ``definition``.

    Descends only where the value has the declared kind, as validation does; values
    of the wrong kind hold no references."""
    shape = definition.shape
    if isinstance(shape, ReferenceShape):
        if isinstance(value, str) and value.strip():
            yield key_path, property_path, shape, value
    elif isinstance(shape, ListShape) and type(value) is list:
        for index, item in enumerate(value):
            yield from _reference_values(
                shape.items, (*key_path, index), f"{property_path}[]", item
            )
    elif isinstance(shape, MapShape) and type(value) is dict:
        for key, item in value.items():
            if isinstance(key, str):
                yield from _reference_values(
                    shape.values, (*key_path, key), f"{property_path}.*", item
                )
    elif isinstance(shape, ObjectShape) and type(value) is dict:
        for name, field_def in shape.fields.items():
            yield from _reference_values(
                field_def, (*key_path, name), f"{property_path}.{name}", value.get(name)
            )
