"""Entity validation against loaded schemas."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from knott._values import BOOLEAN_SPELLINGS, kind, show
from knott.models import Issue
from knott.schema.models import AttributeDef, RelationDef, ScalarType, Schema
from knott.vault.entity import MarkdownFile
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

    for attribute in schema.attributes.values():
        issue = _check_attribute(entity, attribute)
        if issue is not None:
            issues.append(issue)

    relations = 0
    for relation in schema.relations.values():
        rel_issues, count = _check_relation(entity, relation, resolve, lookup)
        issues.extend(rel_issues)
        relations += count
    return EntityReport(issues, relations)


def _check_attribute(entity: MarkdownFile, attribute: AttributeDef) -> Issue | None:
    assert entity.frontmatter is not None
    name = attribute.name
    value = entity.frontmatter.get(name)
    line = entity.key_lines.get(name)
    if is_absent(value):
        if not attribute.required:
            return None
        return Issue(
            code="attribute-missing",
            path=entity.path,
            line=line,
            field=name,
            message=f"required attribute `{name}` ({attribute.type.value}) is missing or empty",
        )
    problem = type_mismatch(attribute.type, value, entity.raw.get(name))
    if problem is None:
        return None
    return Issue(
        code="attribute-type-mismatch",
        path=entity.path,
        line=line,
        field=name,
        message=f"attribute `{name}` {problem}",
    )


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
                    f"relation `{name}` points to `{resolved.destination}`, "
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
                    f"but `{resolved.destination}` has type "
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
