"""Entity validation against loaded schemas."""

from __future__ import annotations

import datetime as dt
import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from knott._values import BOOLEAN_SPELLINGS, kind, show
from knott._yaml import KeyPath
from knott.models import Issue
from knott.schema.models import (
    AttributeDef,
    ListShape,
    MapShape,
    ObjectShape,
    ReferenceShape,
    ScalarType,
    Schema,
    Shape,
    notation,
)
from knott.vault.entity import MarkdownFile
from knott.vault.kid import KID_KEY, is_canonical, kid_problem
from knott.vault.links import LINK_EXAMPLE, LinkError, ResolvedReference

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}")

Resolver = Callable[[str, str], ResolvedReference]
"""(source path, reference) -> resolved reference; raises ``LinkError``."""
FileLookup = Callable[[str], MarkdownFile]


@dataclass(frozen=True)
class EntityReport:
    issues: list[Issue]
    relations: int
    """References that resolved to an entity of the expected type."""


def is_absent(value: Any) -> bool:
    """Attributes: a null or empty-string value counts as absent."""
    return value is None or value == ""


def validate_entity(
    entity: MarkdownFile,
    schemas: dict[str, Schema],
    resolve: Resolver,
    lookup: FileLookup,
) -> EntityReport:
    assert entity.frontmatter is not None
    entity_type = entity.type
    schema = schemas.get(entity_type) if isinstance(entity_type, str) else None
    if schema is None:
        known = ", ".join(f"`{t}`" for t in sorted(schemas)) or "none"
        issue = Issue(
            code="entity-unknown-type",
            path=entity.path,
            line=entity.key_lines.get("type"),
            field="type",
            message=(
                f"type {show(entity_type, entity.raw.get('type'))} has no schema "
                f"in .knott/concepts/ (known types: {known})"
            ),
        )
        return EntityReport([issue], 0)

    checker = _ValueChecker(entity, resolve, lookup)
    checker.issues.extend(_check_kid(entity, schema))
    for name, prop in schema.properties.items():
        checker.check(prop, (name,), entity.frontmatter.get(name))
    return EntityReport(checker.issues, checker.relations)


def _check_kid(entity: MarkdownFile, schema: Schema) -> list[Issue]:
    assert entity.frontmatter is not None
    value = entity.frontmatter.get(KID_KEY)
    if is_absent(value):
        if not schema.kid_required:
            return []
        return [
            Issue(
                code="kid-missing",
                path=entity.path,
                line=entity.key_lines.get(KID_KEY, entity.key_lines.get("type")),
                field=KID_KEY,
                message=(
                    f"`{schema.type}` entities require a `kid`; "
                    "run `knott validate --fix` to add one"
                ),
            )
        ]
    if is_canonical(value):
        return []
    return [
        Issue(
            code="kid-invalid",
            path=entity.path,
            line=entity.key_lines.get(KID_KEY),
            field=KID_KEY,
            message=f"`kid` {kid_problem(value, entity.raw.get(KID_KEY))}",
        )
    ]


def holds_references(shape: Shape) -> bool:
    """A reference, or a list or map whose items are references (at any depth).

    Such a property reports `relation-*` codes rather than `attribute-*` ones
    (amended decision 0005)."""
    if isinstance(shape, ReferenceShape):
        return True
    if isinstance(shape, ListShape):
        return holds_references(shape.items.shape)
    if isinstance(shape, MapShape):
        return holds_references(shape.values.shape)
    return False


class _ValueChecker:
    """Checks one entity's frontmatter values; counts references that resolve."""

    def __init__(self, entity: MarkdownFile, resolve: Resolver, lookup: FileLookup) -> None:
        self.entity = entity
        self.resolve = resolve
        self.lookup = lookup
        self.issues: list[Issue] = []
        self.relations = 0

    def report(self, code: str, message: str, at: KeyPath) -> None:
        self.issues.append(
            Issue(
                code=code,
                path=self.entity.path,
                line=self.entity.line_of(at),
                field=format_field_path(at),
                message=message,
            )
        )

    def check(self, definition: AttributeDef, path: KeyPath, value: Any) -> None:
        """Check ``value`` at ``path`` against ``definition``, descending into lists,
        objects and maps. A value of the wrong kind is reported once, without checking
        its contents."""
        shape = definition.shape
        field = format_field_path(path)
        references = holds_references(shape)
        noun = "relation" if references else "attribute"

        if _is_empty(value, shape):
            if definition.name is None:
                what = "list item" if isinstance(path[-1], int) else "map value"
                if references:
                    self.report(
                        "relation-invalid-value",
                        f"relation `{field}` is an empty {what}; remove it or give it a reference",
                        path,
                    )
                else:
                    self.report(
                        "attribute-type-mismatch",
                        f"attribute `{field}` is an empty {what}; remove it or give it a value",
                        path,
                    )
            elif definition.required:
                code = "relation-missing" if references else "attribute-missing"
                if isinstance(shape, ListShape):
                    hint = "; add at least one " + ("reference" if references else "item")
                elif references:
                    hint = "; add a reference"
                else:
                    hint = ""
                self.report(
                    code,
                    f"required {noun} `{field}` ({notation(shape)}) is missing or empty{hint}",
                    path,
                )
            return

        if isinstance(shape, ReferenceShape):
            self._check_reference(shape, path, value)
            return

        if isinstance(shape, ScalarType):
            problem = type_mismatch(shape, value, self.entity.raws.get(path))
            if problem is not None:
                self.report("attribute-type-mismatch", f"attribute `{field}` {problem}", path)
            return

        if isinstance(shape, ListShape) and type(value) is list:
            for index, item in enumerate(value):
                self.check(shape.items, (*path, index), item)
        elif isinstance(shape, ObjectShape) and type(value) is dict:
            for name, field_def in shape.fields.items():
                self.check(field_def, (*path, name), value.get(name))
            for key in value:
                if key not in shape.fields:
                    self.report(
                        "attribute-unknown-field",
                        _unknown_field_message(field, key, list(shape.fields)),
                        (*path, str(key)),
                    )
        elif isinstance(shape, MapShape) and type(value) is dict:
            for key, item in value.items():
                if isinstance(key, str):
                    self.check(shape.values, (*path, key), item)
                else:
                    code = "relation-invalid-value" if references else "attribute-type-mismatch"
                    self.report(code, _map_key_message(noun, field, key), path)
        elif references:
            raw = self.entity.raws.get(path)
            message = (
                f"relation `{field}` expects {notation(shape)} "
                f"but got {kind(value)} {show(value, raw)}"
            )
            if isinstance(shape, ListShape) and isinstance(value, str):
                message += "; write it as a list of references, even for one"
            self.report("relation-invalid-value", message, path)
        else:
            raw = self.entity.raws.get(path)
            self.report(
                "attribute-type-mismatch",
                f"attribute `{field}` expects {notation(shape)} "
                f"but got {kind(value)} {show(value, raw)}",
                path,
            )

    def _check_reference(self, shape: ReferenceShape, path: KeyPath, value: Any) -> None:
        field = format_field_path(path)
        if type(value) is list:
            if any(type(item) is list for item in value):
                message = _nested_list_hint(field)
            elif not value:
                message = (
                    f"relation `{field}` expects one reference but got an empty list; "
                    "leave the value empty when there is none"
                )
            else:
                message = (
                    f"relation `{field}` expects one reference but got a list; "
                    "declare `type: list` with reference `items` for several"
                )
            self.report("relation-invalid-value", message, path)
            return
        if not isinstance(value, str):
            raw = self.entity.raws.get(path)
            self.report(
                "relation-invalid-value",
                f"relation `{field}` must be a reference string, "
                f"got {kind(value)} {show(value, raw)}",
                path,
            )
            return

        try:
            resolved = self.resolve(self.entity.path, value)
        except LinkError as exc:
            self.report(exc.code, f"relation `{field}`: {exc.message}", path)
            return
        target = self.lookup(resolved.target)
        if not target.is_entity:
            reason = (
                f"its frontmatter is invalid ({target.error})"
                if target.error is not None
                else "it has no frontmatter `type`"
            )
            self.report(
                "relation-target-not-entity",
                f"relation `{field}` points to {resolved.label}, "
                f"which is not a Knott entity: {reason}",
                path,
            )
            return
        if shape.targets and target.type not in shape.targets:
            expected = " or ".join(f"`{t}`" for t in shape.targets)
            self.report(
                "relation-target-type-mismatch",
                f"relation `{field}` expects target type {expected}\n"
                f"but {resolved.label} has type {show(target.type, target.raw.get('type'))}",
                path,
            )
            return
        self.relations += 1


def _is_empty(value: Any, shape: Shape) -> bool:
    """Decision 0005, at every level: null and "" are absent, and so is an empty
    container of the declared kind. An empty container of another kind is a mismatch."""
    if is_absent(value):
        return True
    if type(value) is list and not value:
        return isinstance(shape, ListShape)
    if type(value) is dict and not value:
        return isinstance(shape, ObjectShape | MapShape)
    return False


def format_field_path(path: KeyPath) -> str:
    """``("senses", 1, "ru")`` -> ``senses[1].ru``."""
    text = ""
    for part in path:
        if isinstance(part, int):
            text += f"[{part}]"
        else:
            text += f".{part}" if text else part
    return text


def _unknown_field_message(field: str, key: Any, allowed: list[str]) -> str:
    name = key if isinstance(key, str) else show(key)
    message = f"unknown field `{name}` in attribute `{field}`; allowed fields: {', '.join(allowed)}"
    if isinstance(key, str):
        close = difflib.get_close_matches(key, allowed, n=1)
        if close:
            message += f"; did you mean `{close[0]}`?"
    return message


def _map_key_message(noun: str, field: str, key: Any) -> str:
    message = (
        f"{noun} `{field}` has map key {show(key)}, which YAML reads as {kind(key)}; "
        "map keys must be strings"
    )
    if type(key) is bool:
        return message + "; quote the key (YAML reads unquoted yes/no/on/off as booleans)"
    return message + f'; quote the key, e.g. "{show(key).strip("`")}"'


def type_mismatch(expected: ScalarType, value: Any, raw: str | None = None) -> str | None:
    """Return a description of why ``value`` doesn't match ``expected``, or None."""
    t = type(value)
    if expected is ScalarType.STRING and t is str:
        return None
    if expected is ScalarType.INTEGER and t is int:
        return None
    if expected is ScalarType.NUMBER and t in (int, float):
        return None
    if expected is ScalarType.BOOLEAN and t is bool and (raw is None or raw in BOOLEAN_SPELLINGS):
        return None
    if expected is ScalarType.DATE and (t is dt.date or (t is str and _is_iso_date(value))):
        return None
    if expected is ScalarType.DATETIME and (
        t is dt.datetime or (t is str and _is_iso_datetime(value))
    ):
        return None

    if expected is ScalarType.BOOLEAN and t is bool:
        return f"expects boolean but got {show(value, raw)}; write true or false"
    message = f"expects {expected.value} but got {kind(value)} {show(value, raw)}"
    if expected is ScalarType.STRING and t in (bool, int, float, dt.date, dt.datetime):
        text = raw if raw is not None else str(value)
        message += f'; quote the value (e.g. "{text}") to make it a string'
    elif expected is ScalarType.DATETIME and (t is dt.date or (t is str and _is_iso_date(value))):
        message += "; a datetime needs a time, e.g. 2026-10-06T09:30:00"
    elif expected is ScalarType.DATE and t is dt.datetime:
        message += "; a date must not include a time, e.g. 2026-10-06"
    elif expected in (ScalarType.DATE, ScalarType.DATETIME) and t is str:
        message += "; use ISO 8601 form, e.g. 2026-10-06" + (
            "T09:30:00" if expected is ScalarType.DATETIME else ""
        )
    return message


def _is_iso_date(text: str) -> bool:
    if not _ISO_DATE.match(text):
        return False
    try:
        dt.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _is_iso_datetime(text: str) -> bool:
    if not _ISO_DATETIME.match(text):
        return False
    try:
        dt.datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def _nested_list_hint(field: str) -> str:
    return (
        f"relation `{field}` contains a nested list; an unquoted [[...]] is parsed by YAML "
        f"as a list. Quote the value; note that wikilinks are not supported, so use a "
        f"Markdown link such as {LINK_EXAMPLE}"
    )
