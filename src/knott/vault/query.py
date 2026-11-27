"""Reading entities as data: records, property filters and outgoing references (spec 0016).

Nothing here validates. Records hold the frontmatter values as written; a filter
matches a value only when it has the kind the property declares; the outgoing
references of an entity are walked along its schema exactly as validation walks
them, so each one carries the issue code `validate` would report for it.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from knott._yaml import KeyPath
from knott.errors import KnottError
from knott.models import EntityRecord, OutgoingRef
from knott.schema.models import (
    AttributeDef,
    EnumShape,
    FileShape,
    ListShape,
    MapShape,
    ObjectShape,
    ReferenceShape,
    ScalarType,
    Schema,
    Shape,
    notation,
)
from knott.schema.validator import (
    format_field_path,
    holds_references,
    is_empty,
    type_mismatch,
)
from knott.vault.entity import MarkdownFile
from knott.vault.index import VaultSession
from knott.vault.kid import KID_KEY
from knott.vault.links import INVALID_VALUE, KID_PREFIX, LinkError
from knott.vault.refs import entity_kid, type_name

TYPE_KEY = "type"
RESERVED_FIELDS = ("path", TYPE_KEY, KID_KEY)
NOT_ENTITY = "relation-target-not-entity"
TYPE_MISMATCH = "relation-target-type-mismatch"

_INTEGER = re.compile(r"-?[0-9]+")
_NUMBER = re.compile(r"-?[0-9]+(\.[0-9]+)?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}.*")

EntityResolver = Callable[[str | Path], str]
"""An entity given as a path or ``kid:<uuid>`` -> its vault-relative path; raises ``KnottError``."""


# --- records -------------------------------------------------------------------


def plain_value(value: Any) -> Any:
    """A frontmatter value as written, in a form JSON can hold (dates stay dates).

    A blank string is ``None``. A value JSON has no form for (``.nan``, ``.inf``, a
    binary value, a set) becomes its YAML text, and so does a mapping key that is
    not a string.
    """
    kind = type(value)
    if value is None or kind in (bool, int, dt.date, dt.datetime):
        return value
    if kind is str:
        return value or None
    if kind is float:
        return value if math.isfinite(value) else type_name(value)
    if kind is list:
        return [plain_value(item) for item in value]
    if kind is dict:
        return {
            key if type(key) is str else type_name(key): plain_value(item)
            for key, item in value.items()
        }
    return type_name(value)


def entity_record(
    session: VaultSession, entity: MarkdownFile, fields: list[str] | None
) -> EntityRecord:
    """The record of ``entity``. ``fields`` chooses the properties, in that order;
    ``None`` leaves ``properties`` out; see ``full_record`` for all of them."""
    assert entity.frontmatter is not None
    frontmatter = entity.frontmatter
    properties = (
        None if fields is None else {name: plain_value(frontmatter.get(name)) for name in fields}
    )
    return EntityRecord(
        path=entity.path,
        type=type_name(entity.type),
        kid=entity_kid(session, entity.path),
        properties=properties,
    )


def full_record(session: VaultSession, entity: MarkdownFile) -> EntityRecord:
    """The record of ``entity`` with every frontmatter key but `type` and `kid`, in file order."""
    assert entity.frontmatter is not None
    names = [name for name in entity.frontmatter if name not in (TYPE_KEY, KID_KEY)]
    return entity_record(session, entity, names)


def check_fields(fields: list[str]) -> None:
    """Raises ``KnottError`` for a field name `list` cannot output."""
    seen: set[str] = set()
    for name in fields:
        if not name:
            raise KnottError("a field name is empty; write --fields as `a,b,c`")
        if name in RESERVED_FIELDS:
            raise KnottError(f"`{name}` is always in the output; leave it out of the fields")
        if name in seen:
            raise KnottError(f"field `{name}` is given twice")
        seen.add(name)


# --- filters -------------------------------------------------------------------


class Filter:
    """One ``KEY=VALUE`` condition on a top-level property of a type.

    ``needle`` is the typed value an entity must hold: ``None`` for "absent", a
    vault-relative entity path for a reference, else a value of the property's kind.
    """

    def __init__(self, definition: AttributeDef, needle: Any) -> None:
        assert definition.name is not None
        self.key = definition.name
        self.shape = definition.shape
        self.needle = needle

    def matches(self, session: VaultSession, entity: MarkdownFile) -> bool:
        assert entity.frontmatter is not None
        value = entity.frontmatter.get(self.key)
        if self.needle is None:
            return is_empty(value, self.shape)
        if isinstance(self.shape, ListShape):
            if type(value) is not list:
                return False
            item_shape = self.shape.items.shape
            return any(
                self._equal(session, entity, item_shape, (self.key, index), item)
                for index, item in enumerate(value)
            )
        return self._equal(session, entity, self.shape, (self.key,), value)

    def _equal(
        self, session: VaultSession, entity: MarkdownFile, shape: Shape, at: KeyPath, value: Any
    ) -> bool:
        """Whether ``value`` has the kind ``shape`` declares and equals the needle."""
        needle = self.needle
        if isinstance(shape, ReferenceShape):
            if not isinstance(value, str) or not value.strip():
                return False
            try:
                return bool(session.resolve(entity.path, value).target == needle)
            except LinkError:
                return False
        if isinstance(shape, EnumShape | FileShape):
            return type(value) is str and value == needle
        if not isinstance(shape, ScalarType):
            return False
        if value is None or type_mismatch(shape, value, entity.raws.get(at)) is not None:
            return False
        if shape is ScalarType.DATE:
            return bool(_as_date(value) == needle)
        if shape is ScalarType.DATETIME:
            moment = _as_datetime(value)
            # A moment with an offset never equals one without.
            return (moment.tzinfo is None) == (needle.tzinfo is None) and moment == needle
        if shape is ScalarType.BOOLEAN:
            return value is needle
        return bool(value == needle)


def _as_date(value: Any) -> dt.date:
    return value if type(value) is dt.date else dt.date.fromisoformat(value)


def _as_datetime(value: Any) -> dt.datetime:
    return value if type(value) is dt.datetime else dt.datetime.fromisoformat(value)


def property_of(schema: Schema, key: str) -> AttributeDef:
    """The top-level property ``key`` of ``schema``; raises ``KnottError`` when it has none."""
    definition = schema.properties.get(key)
    if definition is None:
        known = ", ".join(f"`{name}`" for name in schema.properties) or "none"
        raise KnottError(
            f"`{key}` is not a property of `{schema.type}` (its properties: {known}); "
            "a property only a subtype declares is filtered by naming that subtype"
        )
    return definition


def _filter_shape(definition: AttributeDef) -> Shape:
    """The shape one value is compared against: the property's, or its items'.

    Raises ``KnottError`` for a shape that cannot be filtered."""
    shape = definition.shape
    item = shape.items.shape if isinstance(shape, ListShape) else shape
    if isinstance(item, ListShape | ObjectShape | MapShape):
        raise KnottError(
            f"`{definition.name}` ({notation(shape)}) cannot be filtered by a value; "
            f"only `{definition.name}=` (absent) is allowed"
        )
    return item


def filter_from_text(
    definition: AttributeDef, text: str, resolve_entity: EntityResolver, base: Path
) -> Filter:
    """The filter ``KEY=text`` as written on the command line.

    A reference is a path relative to ``base`` or ``kid:<uuid>``. Raises ``KnottError``
    when ``text`` cannot be read as the property's shape."""
    if text == "":
        return Filter(definition, None)
    key = definition.name
    shape = _filter_shape(definition)

    def bad(expected: str) -> KnottError:
        kind = notation(shape)
        return KnottError(f"--where {key}={text}: `{key}` is {kind}; expected {expected}")

    needle: Any
    if isinstance(shape, ReferenceShape):
        given: str | Path = text if text.strip().startswith(KID_PREFIX) else base / text
        needle = resolve_entity(given)
    elif isinstance(shape, EnumShape):
        if text not in shape.names:
            raise bad("one of " + ", ".join(f"`{name}`" for name in shape.names))
        needle = text
    elif isinstance(shape, FileShape) or shape is ScalarType.STRING:
        needle = text
    elif shape is ScalarType.INTEGER:
        if not _INTEGER.fullmatch(text):
            raise bad("an integer, e.g. 3")
        needle = int(text)
    elif shape is ScalarType.NUMBER:
        if not _NUMBER.fullmatch(text):
            raise bad("a number, e.g. 3 or 2.5")
        needle = float(text) if "." in text else int(text)
    elif shape is ScalarType.BOOLEAN:
        if text not in ("true", "false"):
            raise bad("true or false")
        needle = text == "true"
    elif shape is ScalarType.DATE:
        try:
            needle = dt.date.fromisoformat(text) if _DATE.fullmatch(text) else None
        except ValueError:
            needle = None
        if needle is None:
            raise bad("a date, e.g. 2026-10-06")
    else:
        try:
            needle = dt.datetime.fromisoformat(text) if _DATETIME.fullmatch(text) else None
        except ValueError:
            needle = None
        if needle is None:
            raise bad("a datetime, e.g. 2026-10-06T09:30:00")
    return Filter(definition, needle)


def filter_from_value(
    definition: AttributeDef, value: Any, resolve_entity: EntityResolver
) -> Filter:
    """The filter for a typed value (the Python API). ``None`` and ``""`` mean "absent".

    Raises ``KnottError`` when ``value`` is not of the property's kind."""
    if value is None or value == "":
        return Filter(definition, None)
    key = definition.name
    shape = _filter_shape(definition)
    kind = type(value)
    ok: bool
    if isinstance(shape, ReferenceShape):
        if not isinstance(value, str | Path):
            ok = False
        else:
            return Filter(definition, resolve_entity(value))
    elif isinstance(shape, EnumShape):
        ok = kind is str and value in shape.names
    elif isinstance(shape, FileShape) or shape is ScalarType.STRING:
        ok = kind is str
    elif shape is ScalarType.INTEGER:
        ok = kind is int
    elif shape is ScalarType.NUMBER:
        ok = kind in (int, float)
    elif shape is ScalarType.BOOLEAN:
        ok = kind is bool
    elif shape is ScalarType.DATE:
        ok = kind is dt.date
    else:
        ok = kind is dt.datetime
    if not ok:
        expected = (
            "one of " + ", ".join(f"`{name}`" for name in shape.names)
            if isinstance(shape, EnumShape)
            else "an entity path or `kid:<uuid>`"
            if isinstance(shape, ReferenceShape)
            else f"a {notation(shape)} value"
        )
        raise KnottError(
            f"where {key}={value!r}: `{key}` is {notation(shape)}; expected {expected}"
        )
    return Filter(definition, value)


# --- outgoing references -------------------------------------------------------


def outgoing_references(
    session: VaultSession, entity: MarkdownFile, schema: Schema
) -> list[OutgoingRef]:
    """Every value of ``entity``'s declared reference properties, in schema order."""
    assert entity.frontmatter is not None
    found: list[OutgoingRef] = []
    for name, definition in schema.properties.items():
        found.extend(_walk(session, entity, definition, (name,), entity.frontmatter.get(name)))
    return found


def _relation_of(shape: Shape) -> str | None:
    """The relation named by the references a list or map of them holds."""
    while isinstance(shape, ListShape | MapShape):
        shape = shape.items.shape if isinstance(shape, ListShape) else shape.values.shape
    return shape.relation if isinstance(shape, ReferenceShape) else None


def _walk(
    session: VaultSession,
    entity: MarkdownFile,
    definition: AttributeDef,
    at: KeyPath,
    value: Any,
) -> Iterator[OutgoingRef]:
    """Mirrors the validator's walk: one row per reference value, and one per value
    `validate` reports as `relation-invalid-value`."""
    shape = definition.shape

    def invalid() -> OutgoingRef:
        return OutgoingRef(
            field=format_field_path(at),
            relation=_relation_of(shape),
            value=plain_value(value),
            path=None,
            type=None,
            kid=None,
            error=INVALID_VALUE,
        )

    if is_empty(value, shape):
        # An absent property has no reference; an empty list item or map value is malformed.
        if definition.name is None and holds_references(shape):
            yield invalid()
        return
    if isinstance(shape, ReferenceShape):
        yield _resolve(session, entity, shape, at, value) if isinstance(value, str) else invalid()
    elif isinstance(shape, ListShape) and type(value) is list:
        for index, item in enumerate(value):
            yield from _walk(session, entity, shape.items, (*at, index), item)
    elif isinstance(shape, ObjectShape) and type(value) is dict:
        for name, field_def in shape.fields.items():
            yield from _walk(session, entity, field_def, (*at, name), value.get(name))
    elif isinstance(shape, MapShape) and type(value) is dict:
        for key, item in value.items():
            if isinstance(key, str):
                yield from _walk(session, entity, shape.values, (*at, key), item)
            elif holds_references(shape):
                yield invalid()
    elif holds_references(shape):
        yield invalid()


def _resolve(
    session: VaultSession, entity: MarkdownFile, shape: ReferenceShape, at: KeyPath, value: str
) -> OutgoingRef:
    path: str | None = None
    target_type: str | None = None
    kid: str | None = None
    error: str | None = None
    try:
        path = session.resolve(entity.path, value).target
    except LinkError as exc:
        error = exc.code
    if path is not None and not session.included.contains(path):
        error = NOT_ENTITY
    elif path is not None:
        target = session.lookup(path)
        if not target.is_entity:
            error = NOT_ENTITY
        else:
            target_type = type_name(target.type)
            kid = entity_kid(session, path)
            if not shape.accepts_type(target.type):
                error = TYPE_MISMATCH
    return OutgoingRef(
        field=format_field_path(at),
        relation=shape.relation,
        value=value,
        path=path,
        type=target_type,
        kid=kid,
        error=error,
    )
