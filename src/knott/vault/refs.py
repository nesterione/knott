"""Reverse lookup: every reference in the vault that resolves to one entity (spec 0006).

References come from the vault's reference index, grouped by a label: a relation's
inverse, a symmetric relation's name, ``← <relation>``, or ``← <type>.<path>`` for a
property that names no relation. Symmetric groups also hold the entity's own
outgoing references, merged with the incoming ones per linked entity.
"""

from __future__ import annotations

from typing import Any

from knott._values import show
from knott.models import Ref, RefDirection, RefGroup, RefKind
from knott.schema.models import RelationDef
from knott.vault.index import IndexedReference, VaultSession
from knott.vault.kid import KID_KEY, is_canonical

_KIND_ORDER: dict[RefKind, int] = {"inverse": 0, "symmetric": 0, "relation": 0, "property": 1}


def type_name(value: Any) -> str:
    """A frontmatter `type` as text: strings as written, other values in YAML form."""
    return value if isinstance(value, str) else show(value).strip("`")


def entity_kid(session: VaultSession, path: str) -> str | None:
    frontmatter = session.lookup(path).frontmatter or {}
    kid = frontmatter.get(KID_KEY)
    return kid if is_canonical(kid) else None


def reverse_lookup(
    session: VaultSession, relations: dict[str, RelationDef], entity: str
) -> list[RefGroup]:
    """The reverse-lookup groups of ``entity`` (a vault-relative path), in spec order."""
    index = session.references()
    incoming: dict[tuple[RefKind, str, str | None], list[IndexedReference]] = {}
    for ref in index.to(entity):
        incoming.setdefault(_group_key(ref, relations), []).append(ref)
    outgoing: dict[tuple[RefKind, str, str | None], list[IndexedReference]] = {}
    for ref in index.from_(entity):
        key = _group_key(ref, relations)
        if key[0] == "symmetric":
            outgoing.setdefault(key, []).append(ref)

    groups: list[RefGroup] = []
    for key in sorted(
        incoming.keys() | outgoing.keys(), key=lambda k: (_KIND_ORDER[k[0]], k[1], k[2] or "")
    ):
        kind, label, relation = key
        if kind == "symmetric":
            references = _symmetric(session, incoming.get(key, []), outgoing.get(key, []))
        else:
            # Stable: within a source, the index keeps schema order.
            ordered = sorted(incoming[key], key=lambda r: r.source)
            references = [_ref(session, r, r.source, r.source_type, "in") for r in ordered]
        groups.append(RefGroup(label=label, kind=kind, relation=relation, references=references))
    return groups


def _group_key(
    ref: IndexedReference, relations: dict[str, RelationDef]
) -> tuple[RefKind, str, str | None]:
    relation = relations.get(ref.relation) if ref.relation is not None else None
    if relation is None:
        return "property", f"← {ref.source_type}.{ref.property_path}", None
    if relation.inverse is not None:
        return "inverse", relation.inverse, relation.name
    if relation.symmetric:
        return "symmetric", relation.name, relation.name
    return "relation", f"← {relation.name}", relation.name


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
