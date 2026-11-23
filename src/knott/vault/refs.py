"""Reverse lookup: every reference in the vault that resolves to one entity (spec 0006).

References come from the vault's reference index, grouped by a label: a relation's
inverse, a symmetric relation's name, ``← <relation>``, or ``← <type>.<path>`` for a
property that names no relation. Symmetric groups also hold the entity's own
outgoing references, merged with the incoming ones per linked entity.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

import yaml

from knott.models import Ref, RefDirection, RefGroup, RefKind
from knott.vault.index import IndexedReference, VaultSession
from knott.vault.kid import KID_KEY, is_canonical

_KIND_ORDER: dict[RefKind, int] = {"inverse": 0, "symmetric": 0, "relation": 0, "property": 1}

GroupKey = tuple[RefKind, str, str | None]
"""A reverse-lookup group: its kind, label and relation name."""


class RelationLike(Protocol):
    """What grouping needs from a relation: `RelationDef` or `RelationDefinition`."""

    @property
    def name(self) -> str: ...
    @property
    def inverse(self) -> str | None: ...
    @property
    def symmetric(self) -> bool: ...


def group_key(
    relations: Mapping[str, RelationLike],
    relation: str | None,
    source_type: Any,
    property_path: str,
) -> GroupKey:
    """The group of a reference at ``source_type``'s property ``property_path`` (in
    `references()` notation) that names ``relation`` (spec 0006 labels)."""
    definition = relations.get(relation) if relation is not None else None
    if definition is None:
        return "property", f"← {type_name(source_type)}.{property_path}", None
    if definition.inverse is not None:
        return "inverse", definition.inverse, definition.name
    if definition.symmetric:
        return "symmetric", definition.name, definition.name
    return "relation", f"← {definition.name}", definition.name


def group_order(key: GroupKey) -> tuple[int, str, str]:
    """Sort key for groups: relation groups by label (then relation), then property groups."""
    return _KIND_ORDER[key[0]], key[1], key[2] or ""


def type_name(value: Any) -> str:
    """A frontmatter `type` as text: strings as written, other values in YAML form."""
    if isinstance(value, str):
        return value
    text = yaml.safe_dump(
        value, default_flow_style=True, allow_unicode=True, sort_keys=False, width=float("inf")
    ).strip()
    # A plain scalar is dumped as a document with an explicit end marker.
    return text.removesuffix("\n...")


def entity_kid(session: VaultSession, path: str) -> str | None:
    frontmatter = session.lookup(path).frontmatter or {}
    kid = frontmatter.get(KID_KEY)
    return kid if is_canonical(kid) else None


def reverse_lookup(
    session: VaultSession, relations: Mapping[str, RelationLike], entity: str
) -> list[RefGroup]:
    """The reverse-lookup groups of ``entity`` (a vault-relative path), in spec order."""
    index = session.references()
    incoming: dict[GroupKey, list[IndexedReference]] = {}
    for ref in index.to(entity):
        incoming.setdefault(_key(ref, relations), []).append(ref)
    outgoing: dict[GroupKey, list[IndexedReference]] = {}
    for ref in index.from_(entity):
        key = _key(ref, relations)
        if key[0] == "symmetric":
            outgoing.setdefault(key, []).append(ref)

    groups: list[RefGroup] = []
    for key in sorted(incoming.keys() | outgoing.keys(), key=group_order):
        kind, label, relation = key
        if kind == "symmetric":
            references = _symmetric(session, incoming.get(key, []), outgoing.get(key, []))
        else:
            # Stable: within a source, the index keeps schema order.
            ordered = sorted(incoming[key], key=lambda r: r.source)
            references = [_ref(session, r, r.source, r.source_type, "in") for r in ordered]
        groups.append(RefGroup(label=label, kind=kind, relation=relation, references=references))
    return groups


def _key(ref: IndexedReference, relations: Mapping[str, RelationLike]) -> GroupKey:
    return group_key(relations, ref.relation, ref.source_type, ref.property_path)


def _symmetric(
    session: VaultSession,
    incoming: list[IndexedReference],
    outgoing: list[IndexedReference],
) -> list[Ref]:
    """One entry per linked entity. Field and line are where the link is stored: the
    linked entity's first reference when it has one, else the entity's own."""
    first_in: dict[str, IndexedReference] = {}
    for ref in incoming:
        first_in.setdefault(ref.source, ref)
    first_out: dict[str, IndexedReference] = {}
    for ref in outgoing:
        first_out.setdefault(ref.target, ref)
    references: list[Ref] = []
    for linked in sorted(first_in.keys() | first_out.keys()):
        ref_in = first_in.get(linked)
        ref_out = first_out.get(linked)
        if ref_in is not None:
            direction: RefDirection = "both" if ref_out is not None else "in"
            references.append(_ref(session, ref_in, linked, ref_in.source_type, direction))
        else:
            assert ref_out is not None
            references.append(_ref(session, ref_out, linked, ref_out.target_type, "out"))
    return references


def _ref(
    session: VaultSession,
    ref: IndexedReference,
    linked: str,
    linked_type: Any,
    direction: RefDirection,
) -> Ref:
    return Ref(
        path=linked,
        type=type_name(linked_type),
        kid=entity_kid(session, linked),
        field=ref.field,
        line=ref.line,
        direction=direction,
    )
