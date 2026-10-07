"""Schema discovery and parsing: ``.knott/schemas/**/*.yaml``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from knott import _yaml
from knott._values import BOOLEAN_SPELLINGS, kind, show
from knott.models import Issue
from knott.schema.models import AttributeDef, RelationDef, ScalarType, Schema
from knott.vault.discovery import KNOTT_DIR

SCHEMAS_DIR = Path(KNOTT_DIR) / "schemas"
TYPE_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")

_TOP_KEYS = ("type", "description", "attributes", "relations")
_ATTRIBUTE_KEYS = ("type", "required", "description")
_RELATION_KEYS = ("target", "required", "description")
_SCALAR_TYPES = ", ".join(t.value for t in ScalarType)


def discover_schema_files(root: Path) -> list[str]:
    schemas_dir = root / SCHEMAS_DIR
    if not schemas_dir.is_dir():
        return []
    return sorted(
        p.relative_to(root).as_posix() for p in schemas_dir.rglob("*.yaml") if p.is_file()
    )


def load_schemas(root: Path) -> tuple[dict[str, Schema], list[Issue]]:
    """Load every schema. Returns the usable schemas by type, and all schema issues."""
    issues: list[Issue] = []
    registry: dict[str, Schema] = {}
    for rel_path in discover_schema_files(root):
        parser = _SchemaParser(rel_path, issues)
        schema = parser.parse(root / rel_path)
        if schema is None:
            continue
        existing = registry.get(schema.type)
        if existing is not None:
            issues.append(
                Issue(
                    code="schema-duplicate-type",
                    path=rel_path,
                    line=parser.line(("type",)),
                    field="type",
                    message=(
                        f"type `{schema.type}` is defined twice: in `{existing.path}` "
                        f"and in `{rel_path}`\n"
                        "each type must be defined by exactly one schema file"
                    ),
                )
            )
            continue
        registry[schema.type] = schema

    for schema in registry.values():
        for name, relation in list(schema.relations.items()):
            if relation.target not in registry:
                known = ", ".join(f"`{t}`" for t in sorted(registry)) or "none"
                issues.append(
                    Issue(
                        code="schema-unknown-target",
                        path=schema.path,
                        line=relation.line,
                        field=f"relations.{name}.target",
                        message=(
                            f"relation `{name}` targets type `{relation.target}`, "
                            f"which no schema defines (known types: {known})"
                        ),
                    )
                )
                schema.unknown_relations[name] = schema.relations.pop(name)
    return registry, issues


class _SchemaParser:
    def __init__(self, rel_path: str, issues: list[Issue]) -> None:
        self.path = rel_path
        self.issues = issues
        self.locs: dict[_yaml.KeyPath, _yaml.Loc] = {}

    def line(self, key_path: _yaml.KeyPath) -> int | None:
        loc = self.locs.get(key_path)
        return loc.line + 1 if loc is not None else None

    def error(self, code: str, key_path: _yaml.KeyPath, message: str) -> None:
        field = ".".join(str(p) for p in key_path) or None
        self.issues.append(
            Issue(code=code, path=self.path, line=self.line(key_path), field=field, message=message)
        )

    def parse(self, abs_path: Path) -> Schema | None:
        try:
            text = abs_path.read_text(encoding="utf-8").removeprefix("﻿")
        except (OSError, UnicodeDecodeError) as exc:
            self.issues.append(
                Issue(code="schema-invalid-yaml", path=self.path, message=f"cannot read: {exc}")
            )
            return None
        try:
            doc = _yaml.load(text)
        except _yaml.YamlParseError as exc:
            line = exc.line + 1 if exc.line is not None else None
            self.issues.append(
                Issue(code="schema-invalid-yaml", path=self.path, line=line, message=exc.message)
            )
            return None
        self.locs = doc.locs
        data = doc.data
        if not isinstance(data, dict):
            actual = "empty" if data is None else f"a {kind(data)}"
            self.issues.append(
                Issue(
                    code="schema-invalid-yaml",
                    path=self.path,
                    message=f"schema file must be a YAML mapping, but it is {actual}",
                )
            )
            return None

        self._check_keys(data, (), _TOP_KEYS)
        type_name = self._check_type(data)
        description = self._optional_str(data, ("description",))
        attributes = self._parse_attributes(data.get("attributes"))
        relations = self._parse_relations(data.get("relations"))
        for name in sorted(set(attributes) & set(relations)):
            self.error(
                "schema-field-conflict",
                ("relations", name),
                f"field `{name}` is declared both as an attribute and as a relation",
            )
            del relations[name]
        if type_name is None:
            return None
        return Schema(
            type=type_name,
            path=self.path,
            description=description,
            attributes=attributes,
            relations=relations,
        )

    def _check_keys(
        self, mapping: dict[Any, Any], path: _yaml.KeyPath, allowed: tuple[str, ...]
    ) -> None:
        for key in mapping:
            if key not in allowed:
                where = "schema" if not path else f"`{'.'.join(str(p) for p in path)}`"
                self.error(
                    "schema-invalid-field",
                    (*path, str(key)),
                    f"unknown key `{key}` in {where}; allowed keys: {', '.join(allowed)}",
                )

    def _check_type(self, data: dict[Any, Any]) -> str | None:
        if "type" not in data or data["type"] is None:
            self.error("schema-invalid-field", ("type",), "missing required key `type`")
            return None
        value = data["type"]
        if not isinstance(value, str) or not TYPE_NAME.match(value):
            self.error(
                "schema-invalid-field",
                ("type",),
                f"type name must match ^[a-z][a-z0-9_-]*$, got {show(value)}",
            )
            return None
        return value

    def _optional_str(self, mapping: dict[Any, Any], key_path: _yaml.KeyPath) -> str | None:
        value = mapping.get(key_path[-1])
        if value is None or isinstance(value, str):
            return value
        self.error(
            "schema-invalid-field", key_path, f"expected a string, got {kind(value)} {show(value)}"
        )
        return None

    def _required_flag(self, mapping: dict[Any, Any], key_path: _yaml.KeyPath) -> bool:
        value = mapping.get("required", False)
        if value is None:
            return False
        loc = self.locs.get(key_path)
        if type(value) is bool and (loc is None or loc.raw in BOOLEAN_SPELLINGS):
            return value
        self.error(
            "schema-invalid-field",
            key_path,
            f"`required` must be true or false, got {kind(value)} {show(value)}",
        )
        return False

    def _fields(self, section: str, value: Any) -> list[tuple[str, dict[Any, Any]]]:
        """Validate a field-definition section; return (name, definition) pairs to parse."""
        if value is None:
            return []
        if not isinstance(value, dict):
            self.error(
                "schema-invalid-field",
                (section,),
                f"`{section}` must be a mapping of field name to definition, got {kind(value)}",
            )
            return []
        result: list[tuple[str, dict[Any, Any]]] = []
        for name, definition in value.items():
            if not isinstance(name, str):
                self.error(
                    "schema-invalid-field",
                    (section, str(name)),
                    f"field name must be a string, got {kind(name)} {show(name)}",
                )
                continue
            if name == "type":
                self.error(
                    "schema-field-conflict",
                    (section, name),
                    "a field cannot be named `type`; it is reserved for the entity type",
                )
                continue
            if not isinstance(definition, dict):
                self.error(
                    "schema-invalid-field",
                    (section, name),
                    f"definition of `{name}` must be a mapping, got {kind(definition)}",
                )
                continue
            result.append((name, definition))
        return result

    def _parse_attributes(self, value: Any) -> dict[str, AttributeDef]:
        attributes: dict[str, AttributeDef] = {}
        for name, definition in self._fields("attributes", value):
            base = ("attributes", name)
            self._check_keys(definition, base, _ATTRIBUTE_KEYS)
            required = self._required_flag(definition, (*base, "required"))
            description = self._optional_str(definition, (*base, "description"))
            raw_type = definition.get("type")
            if raw_type is None:
                self.error(
                    "schema-invalid-field",
                    base,
                    f"attribute `{name}` is missing `type` (one of: {_SCALAR_TYPES})",
                )
                continue
            try:
                scalar = ScalarType(raw_type) if isinstance(raw_type, str) else None
            except ValueError:
                scalar = None
            if scalar is None:
                self.error(
                    "schema-invalid-field",
                    (*base, "type"),
                    f"unknown attribute type {show(raw_type)}; expected one of: {_SCALAR_TYPES}",
                )
                continue
            attributes[name] = AttributeDef(name, scalar, required, description)
        return attributes

    def _parse_relations(self, value: Any) -> dict[str, RelationDef]:
        relations: dict[str, RelationDef] = {}
        for name, definition in self._fields("relations", value):
            base = ("relations", name)
            self._check_keys(definition, base, _RELATION_KEYS)
            required = self._required_flag(definition, (*base, "required"))
            description = self._optional_str(definition, (*base, "description"))
            target = definition.get("target")
            if target is None:
                self.error("schema-invalid-field", base, f"relation `{name}` is missing `target`")
                continue
            if not isinstance(target, str):
                self.error(
                    "schema-invalid-field",
                    (*base, "target"),
                    f"`target` must be a type name, got {kind(target)} {show(target)}",
                )
                continue
            line = self.line((*base, "target"))
            relations[name] = RelationDef(name, target, required, description, line)
        return relations
