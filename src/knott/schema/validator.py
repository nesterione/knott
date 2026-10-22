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
    RelationDef,
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


def is_absent_relation(value: Any) -> bool:
    """Relations: null, empty string, or an empty list counts as absent."""
    return is_absent(value) or value == []


def validate_entity(
    entity: MarkdownFile,
    schemas: dict[str, Schema],
    resolve: Resolver,
    lookup: FileLookup,
) -> EntityReport:
    assert entity.frontmatter is not None
    issues: list[Issue] = []
    entity_type = entity.type
    schema = schemas.get(entity_type) if isinstance(entity_type, str) else None
    if schema is None:
        known = ", ".join(f"`{t}`" for t in sorted(schemas)) or "none"
        issues.append(
            Issue(
                code="entity-unknown-type",
                path=entity.path,
                line=entity.key_lines.get("type"),
                field="type",
                message=(
                    f"type {show(entity_type, entity.raw.get('type'))} has no schema "
                    f"in .knott/schemas/ (known types: {known})"
                ),
            )
        )
        return EntityReport(issues, 0)

    issues.extend(_check_kid(entity, schema))
    for attribute in schema.attributes.values():
        issues.extend(_check_attribute(entity, attribute))

    relations = 0
    for relation in schema.relations.values():
        rel_issues, count = _check_relation(entity, relation, resolve, lookup)
        issues.extend(rel_issues)
        relations += count
    return EntityReport(issues, relations)


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


def _check_attribute(entity: MarkdownFile, attribute: AttributeDef) -> list[Issue]:
    assert entity.frontmatter is not None and attribute.name is not None
    issues: list[Issue] = []
    path: KeyPath = (attribute.name,)
    _check_value(entity, attribute, path, entity.frontmatter.get(attribute.name), issues)
    return issues


def _check_value(
    entity: MarkdownFile,
    definition: AttributeDef,
    path: KeyPath,
    value: Any,
    issues: list[Issue],
) -> None:
    """Check ``value`` at ``path`` against ``definition``, descending into lists, objects
    and maps. A value of the wrong kind is reported once, without checking its contents."""
    shape = definition.shape
    field = format_field_path(path)

    def report(code: str, message: str, at: KeyPath = path) -> None:
        issues.append(
            Issue(
                code=code,
                path=entity.path,
                line=entity.line_of(at),
                field=format_field_path(at),
                message=message,
            )
        )

    if _is_empty(value, shape):
        if definition.name is None:
            what = "list item" if isinstance(path[-1], int) else "map value"
            report(
                "attribute-type-mismatch",
                f"attribute `{field}` is an empty {what}; remove it or give it a value",
            )
        elif definition.required:
            hint = "; add at least one item" if isinstance(shape, ListShape) else ""
            report(
                "attribute-missing",
                f"required attribute `{field}` ({notation(shape)}) is missing or empty{hint}",
            )
        return

    if isinstance(shape, ScalarType):
        problem = type_mismatch(shape, value, entity.raws.get(path))
        if problem is not None:
            report("attribute-type-mismatch", f"attribute `{field}` {problem}")
        return

    raw = entity.raws.get(path)
    if isinstance(shape, ListShape) and type(value) is list:
        for index, item in enumerate(value):
            _check_value(entity, shape.items, (*path, index), item, issues)
    elif isinstance(shape, ObjectShape) and type(value) is dict:
        for name, field_def in shape.fields.items():
            _check_value(entity, field_def, (*path, name), value.get(name), issues)
        for key in value:
            if key not in shape.fields:
                report(
                    "attribute-unknown-field",
                    _unknown_field_message(field, key, list(shape.fields)),
                    (*path, str(key)),
                )
    elif isinstance(shape, MapShape) and type(value) is dict:
        for key, item in value.items():
            if isinstance(key, str):
                _check_value(entity, shape.values, (*path, key), item, issues)
            else:
                report("attribute-type-mismatch", _map_key_message(field, key))
    else:
        report(
            "attribute-type-mismatch",
            f"attribute `{field}` expects {notation(shape)} "
            f"but got {kind(value)} {show(value, raw)}",
        )


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


def _map_key_message(field: str, key: Any) -> str:
    message = (
        f"attribute `{field}` has map key {show(key)}, which YAML reads as {kind(key)}; "
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


def _check_relation(
    entity: MarkdownFile,
    relation: RelationDef,
    resolve: Resolver,
    lookup: FileLookup,
) -> tuple[list[Issue], int]:
    assert entity.frontmatter is not None
    name = relation.name
    value = entity.frontmatter.get(name)
    key_line = entity.key_lines.get(name)

    def issue(code: str, message: str, line: int | None = key_line) -> Issue:
        return Issue(code=code, path=entity.path, line=line, field=name, message=message)

    if is_absent_relation(value):
        if not relation.required:
            return [], 0
        return [
            issue(
                "relation-missing",
                f"required relation `{name}` (target type `{relation.target}`) "
                "is missing or empty; add at least one reference",
            )
        ], 0

    references: list[tuple[str, int | None]] = []
    if isinstance(value, str):
        references.append((value, key_line))
    elif isinstance(value, list):
        problems: list[Issue] = []
        for index, item in enumerate(value):
            item_line = entity.item_lines.get((name, index), key_line)
            if isinstance(item, str) and item:
                references.append((item, item_line))
            elif isinstance(item, list):
                problems.append(issue("relation-invalid-value", _nested_list_hint(name), item_line))
            else:
                problems.append(
                    issue(
                        "relation-invalid-value",
                        f"relation `{name}` item {index + 1} must be a non-empty string, "
                        f"got {kind(item)} {show(item)}",
                        item_line,
                    )
                )
        if problems:
            return problems, 0
    else:
        return [
            issue(
                "relation-invalid-value",
                f"relation `{name}` must be a reference string or a list of them, "
                f"got {kind(value)} {show(value, entity.raw.get(name))}",
            )
        ], 0

    issues: list[Issue] = []
    resolved_count = 0
    for reference, line in references:
        try:
            resolved = resolve(entity.path, reference)
        except LinkError as exc:
            issues.append(issue(exc.code, f"relation `{name}`: {exc.message}", line))
            continue
        target = lookup(resolved.target)
        if not target.is_entity:
            reason = (
                f"its frontmatter is invalid ({target.error})"
                if target.error is not None
                else "it has no frontmatter `type`"
            )
            issues.append(
                issue(
                    "relation-target-not-entity",
                    f"relation `{name}` points to {resolved.label}, "
                    f"which is not a Knott entity: {reason}",
                    line,
                )
            )
            continue
        if target.type != relation.target:
            issues.append(
                issue(
                    "relation-target-type-mismatch",
                    f"relation `{name}` expects target type `{relation.target}`\n"
                    f"but {resolved.label} has type "
                    f"{show(target.type, target.raw.get('type'))}",
                    line,
                )
            )
            continue
        resolved_count += 1
    return issues, resolved_count


def _nested_list_hint(name: str) -> str:
    return (
        f"relation `{name}` contains a nested list; an unquoted [[...]] is parsed by YAML "
        f"as a list. Quote the value; note that wikilinks are not supported, so use a "
        f"Markdown link such as {LINK_EXAMPLE}"
    )
