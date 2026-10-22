"""Schema discovery and parsing: ``.knott/schemas/**/*.yaml``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from knott import _yaml
from knott._values import BOOLEAN_SPELLINGS, kind, show
from knott.models import Issue
from knott.schema.models import (
    COMPOUND_KINDS,
    AttributeDef,
    ListShape,
    MapShape,
    ObjectShape,
    RelationDef,
    ScalarType,
    Schema,
    Shape,
)
from knott.vault.discovery import KNOTT_DIR

SCHEMAS_DIR = Path(KNOTT_DIR) / "schemas"
TYPE_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")

_TOP_KEYS = ("type", "description", "kid", "attributes", "relations")
# Top-level frontmatter keys that belong to knott, not to a schema's fields.
_RESERVED_FIELDS = {
    "type": "it is reserved for the entity type",
    "kid": "it is reserved for the knott-managed entity identity",
}
_DEFINITION_KEYS = ("type", "required", "description")
_RELATION_KEYS = ("target", "required", "description")
_ATTRIBUTE_TYPES = ", ".join([*(t.value for t in ScalarType), *COMPOUND_KINDS])
# The key that nests the inner definition, by compound kind.
_NESTING_KEYS = {"list": "items", "object": "fields", "map": "values"}
_NESTING_EXAMPLES = {
    "list": "items: {type: string}",
    "object": "fields: {name: {type: string}}",
    "map": "values: {type: string}",
}


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
        kid_required = self._kid_required(data)
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
            kid_required=kid_required,
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

    def _kid_required(self, data: dict[Any, Any]) -> bool:
        value = data.get("kid")
        if value is None or value == "required":
            return value == "required"
        self.error(
            "schema-invalid-field",
            ("kid",),
            f"`kid` must be `required`, got {show(value)}; omit it to make `kid` optional",
        )
        return False

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

    def _fields(self, base: _yaml.KeyPath, value: Any) -> list[tuple[str, dict[Any, Any]]]:
        """Validate a field-definition section; return (name, definition) pairs to parse."""
        if value is None:
            return []
        where = ".".join(str(p) for p in base)
        if not isinstance(value, dict):
            self.error(
                "schema-invalid-field",
                base,
                f"`{where}` must be a mapping of field name to definition, got {kind(value)}",
            )
            return []
        result: list[tuple[str, dict[Any, Any]]] = []
        for name, definition in value.items():
            if not isinstance(name, str):
                self.error(
                    "schema-invalid-field",
                    (*base, str(name)),
                    f"field name must be a string, got {kind(name)} {show(name)}",
                )
                continue
            # Only top-level fields share the frontmatter with `type` and `kid`.
            if name in _RESERVED_FIELDS and len(base) == 1:
                self.error(
                    "schema-field-conflict",
                    (*base, name),
                    f"a field cannot be named `{name}`; {_RESERVED_FIELDS[name]}",
                )
                continue
            if not isinstance(definition, dict):
                self.error(
                    "schema-invalid-field",
                    (*base, name),
                    f"definition of `{name}` must be a mapping, got {kind(definition)}",
                )
                continue
            result.append((name, definition))
        return result

    def _parse_attributes(self, value: Any) -> dict[str, AttributeDef]:
        attributes: dict[str, AttributeDef] = {}
        for name, definition in self._fields(("attributes",), value):
            attribute = self._parse_definition(definition, ("attributes", name), name)
            if attribute is not None:
                attributes[name] = attribute
        return attributes

    def _parse_definition(
        self, definition: dict[Any, Any], base: _yaml.KeyPath, name: str | None
    ) -> AttributeDef | None:
        """Parse an attribute, an object field, or a list's `items` / map's `values` (no name).

        Returns None when anything inside is invalid; every problem is still reported.
        """
        raw_type = definition.get("type")
        kind_name = _kind_name(raw_type)
        self._check_definition_keys(definition, base, kind_name, nested=name is None)
        required = False
        if name is not None:
            required = self._required_flag(definition, (*base, "required"))
        description = self._optional_str(definition, (*base, "description"))
        label = f"attribute `{name}`" if len(base) == 2 else f"`{'.'.join(map(str, base))}`"
        if raw_type is None:
            self.error(
                "schema-invalid-field",
                base,
                f"{label} is missing `type` (one of: {_ATTRIBUTE_TYPES})",
            )
            return None
        if kind_name is None:
            self.error(
                "schema-invalid-field",
                (*base, "type"),
                f"unknown attribute type {show(raw_type)}; expected one of: {_ATTRIBUTE_TYPES}",
            )
            return None
        shape = self._parse_shape(kind_name, definition, base, label)
        if shape is None:
            return None
        return AttributeDef(name, shape, required, description)

    def _check_definition_keys(
        self,
        definition: dict[Any, Any],
        base: _yaml.KeyPath,
        kind_name: str | None,
        nested: bool,
    ) -> None:
        allowed = [k for k in _DEFINITION_KEYS if not (nested and k == "required")]
        if kind_name in _NESTING_KEYS:
            allowed.append(_NESTING_KEYS[kind_name])
        for key in definition:
            if key == "required" and nested:
                container = "list" if base[-1] == "items" else "map"
                self.error(
                    "schema-invalid-field",
                    (*base, "required"),
                    f"`required` is not allowed on `{base[-1]}`: an item or value can never "
                    f"be empty; put `required` on the {container} itself",
                )
            elif key in _NESTING_KEYS.values():
                owner = next(k for k, v in _NESTING_KEYS.items() if v == key)
                if kind_name is not None and kind_name != owner:
                    self.error(
                        "schema-invalid-field",
                        (*base, key),
                        f"`{key}` is only allowed when `type` is {owner}, "
                        f"but `type` is {kind_name}",
                    )
            elif key not in _DEFINITION_KEYS:
                where = ".".join(str(p) for p in base)
                self.error(
                    "schema-invalid-field",
                    (*base, str(key)),
                    f"unknown key `{key}` in `{where}`; allowed keys: {', '.join(allowed)}",
                )

    def _parse_shape(
        self, kind_name: str, definition: dict[Any, Any], base: _yaml.KeyPath, label: str
    ) -> Shape | None:
        if kind_name not in _NESTING_KEYS:
            return ScalarType(kind_name)
        key = _NESTING_KEYS[kind_name]
        inner = definition.get(key)
        if inner is None:
            self.error(
                "schema-invalid-field",
                base,
                f"{label} has type {kind_name} but no `{key}`, e.g. {_NESTING_EXAMPLES[kind_name]}",
            )
            return None
        if kind_name == "object":
            return self._parse_object(inner, (*base, key))
        if not isinstance(inner, dict):
            self.error(
                "schema-invalid-field",
                (*base, key),
                f"`{key}` must be a mapping (a definition with `type`), got {kind(inner)}, "
                f"e.g. {_NESTING_EXAMPLES[kind_name]}",
            )
            return None
        node = self._parse_definition(inner, (*base, key), None)
        if node is None:
            return None
        return ListShape(node) if kind_name == "list" else MapShape(node)

    def _parse_object(self, value: Any, base: _yaml.KeyPath) -> ObjectShape | None:
        if not isinstance(value, dict) or not value:
            got = "an empty mapping" if isinstance(value, dict) else kind(value)
            self.error(
                "schema-invalid-field",
                base,
                f"`fields` must map at least one field name to its definition, got {got}; "
                "use `type: map` for free-form keys",
            )
            return None
        fields: dict[str, AttributeDef] = {}
        for name, definition in self._fields(base, value):
            node = self._parse_definition(definition, (*base, name), name)
            if node is not None:
                fields[name] = node
        if len(fields) != len(value):
            return None
        return ObjectShape(fields)

    def _parse_relations(self, value: Any) -> dict[str, RelationDef]:
        relations: dict[str, RelationDef] = {}
        for name, definition in self._fields(("relations",), value):
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


def _kind_name(raw_type: Any) -> str | None:
    """The attribute kind named by a schema `type` value, or None if it names none."""
    if not isinstance(raw_type, str):
        return None
    if raw_type in COMPOUND_KINDS or raw_type in {t.value for t in ScalarType}:
        return raw_type
    return None
