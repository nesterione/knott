"""Concept discovery and parsing: ``.knott/concepts/**/*.md`` (decision 0010)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from knott import _yaml
from knott._values import BOOLEAN_SPELLINGS, kind, show
from knott.models import Issue
from knott.schema.connectors import load_connectors
from knott.schema.models import (
    COMPOUND_KINDS,
    FILE_KIND,
    REFERENCE_KIND,
    AttributeDef,
    ConnectorDef,
    FileShape,
    ListShape,
    MapShape,
    ObjectShape,
    ReferenceShape,
    RelationDef,
    ScalarType,
    Schema,
    SchemaPath,
    Shape,
)
from knott.schema.relations import check_definitions, load_relations
from knott.vault.discovery import CONCEPTS_DIR, LEGACY_SCHEMAS_DIR
from knott.vault.entity import MarkdownFile, markdown_body, parse_markdown

TYPE_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")

_TOP_KEYS = ("name", "description", "kid", "properties")
# Top-level keys with a targeted hint instead of the generic "unknown key".
_TOP_KEY_HINTS = {
    "type": "concept files use `name:`; `type:` belongs to entities",
    "attributes": "merged into `properties` (decision 0010); run `knott migrate`",
    "relations": "merged into `properties` (decision 0010); run `knott migrate`",
}
# Top-level frontmatter keys that belong to knott, not to a concept's properties.
_RESERVED_FIELDS = {
    "type": "it is reserved for the entity type",
    "kid": "it is reserved for the knott-managed entity identity",
}
_DEFINITION_KEYS = ("type", "required", "description")
_PROPERTY_TYPES = ", ".join(
    [*(t.value for t in ScalarType), *COMPOUND_KINDS, REFERENCE_KIND, FILE_KIND]
)
_EXTENSION = re.compile(r"^[a-z0-9]+$")
# The key that nests the inner definition, by kind.
_NESTING_KEYS = {"list": "items", "object": "fields", "map": "values", REFERENCE_KIND: "target"}
_NESTING_EXAMPLES = {
    "list": "items: {type: string}",
    "object": "fields: {name: {type: string}}",
    "map": "values: {type: string}",
    REFERENCE_KIND: "target: script",
}


def discover_schema_files(root: Path) -> list[str]:
    """Vault-relative paths of every concept file, sorted."""
    concepts_dir = root / CONCEPTS_DIR
    if not concepts_dir.is_dir():
        return []
    return sorted(p.relative_to(root).as_posix() for p in concepts_dir.rglob("*.md") if p.is_file())


def legacy_layout_issue() -> Issue:
    return Issue(
        code="schema-legacy-layout",
        path=LEGACY_SCHEMAS_DIR,
        message=(
            f"`{LEGACY_SCHEMAS_DIR}/` is the pre-0.5 schema layout; knott now reads concept "
            f"files from `{CONCEPTS_DIR}/` (decision 0010)\n"
            "run `knott migrate` to convert the schemas, then review the diff"
        ),
    )


def load_schemas(root: Path) -> tuple[dict[str, Schema], list[Issue]]:
    """Load every concept. Returns the usable schemas by type, and all schema issues.

    Relation files are loaded and checked too; their issues are included.
    """
    schemas, _, issues = load_ontology(root)
    return schemas, issues


def load_ontology(root: Path) -> tuple[dict[str, Schema], dict[str, RelationDef], list[Issue]]:
    """Load every concept and relation file (spec 0006).

    Returns the usable schemas by type, the usable relations by name, and all
    schema issues (connector files included). A vault that still has
    ``.knott/schemas/`` gets one ``schema-legacy-layout`` issue and empty registries.
    """
    loaded = load_definitions(root)
    return loaded.schemas, loaded.relations, loaded.issues


@dataclass
class Definitions:
    """Everything ``.knott/`` defines, with the problems found while loading it."""

    schemas: dict[str, Schema] = field(default_factory=dict)
    relations: dict[str, RelationDef] = field(default_factory=dict)
    connectors: dict[str, ConnectorDef] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)


def load_definitions(root: Path) -> Definitions:
    """Load every concept, relation and connector file (specs 0006 and 0008)."""
    if (root / LEGACY_SCHEMAS_DIR).exists():
        return Definitions(issues=[legacy_layout_issue()])
    issues: list[Issue] = []
    registry: dict[str, Schema] = {}
    parsers: dict[str, _SchemaParser] = {}
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
                    line=parser.line(("name",)),
                    field="name",
                    message=(
                        f"concept `{schema.type}` is defined twice: in `{existing.path}` "
                        f"and in `{rel_path}`\n"
                        "each concept must be defined by exactly one concept file"
                    ),
                )
            )
            continue
        registry[schema.type] = schema
        parsers[schema.type] = parser

    relations = load_relations(root, issues)
    for schema in registry.values():
        parser = parsers[schema.type]
        schema.properties = {
            name: _resolve_targets(definition, (name,), registry, relations, parser)
            for name, definition in schema.properties.items()
        }
    check_definitions(
        registry,
        relations,
        lambda schema, path: parsers[schema.type].relation_line(path),
        issues,
    )
    connectors = load_connectors(root, issues)
    return Definitions(registry, relations, connectors, issues)


def _resolve_targets(
    definition: AttributeDef,
    path: SchemaPath,
    registry: dict[str, Schema],
    relations: dict[str, RelationDef],
    parser: _SchemaParser,
) -> AttributeDef:
    """Move target types no concept defines into ``ReferenceShape.unknown``, reporting each.

    A relation no relation file defines is reported and dropped: the reference
    still works as a plain reference.
    """
    shape = definition.shape
    new_shape: Shape = shape
    if isinstance(shape, ReferenceShape):
        known = tuple(t for t in shape.targets if t in registry)
        unknown = tuple(t for t in shape.targets if t not in registry)
        for target in unknown:
            parser.unknown_target(path, target, registry)
        relation = shape.relation
        if relation is not None and relation not in relations:
            parser.unknown_relation(path, relation, relations)
            relation = None
        new_shape = ReferenceShape(known, unknown, relation)
    elif isinstance(shape, ListShape):
        new_shape = ListShape(
            _resolve_targets(shape.items, (*path, "items"), registry, relations, parser)
        )
    elif isinstance(shape, MapShape):
        new_shape = MapShape(
            _resolve_targets(shape.values, (*path, "values"), registry, relations, parser)
        )
    elif isinstance(shape, ObjectShape):
        new_shape = ObjectShape(
            {
                name: _resolve_targets(
                    field_def, (*path, "fields", name), registry, relations, parser
                )
                for name, field_def in shape.fields.items()
            }
        )
    if new_shape is shape:
        return definition
    return AttributeDef(definition.name, new_shape, definition.required, definition.description)


class _SchemaParser:
    def __init__(self, rel_path: str, issues: list[Issue]) -> None:
        self.path = rel_path
        self.issues = issues
        self.file = MarkdownFile(path=rel_path)
        self.target_lines: dict[SchemaPath, dict[str, int | None]] = {}
        """Line of each target name, by the reference's path inside `properties`."""

    def line(self, key_path: _yaml.KeyPath) -> int | None:
        return self.file.lines.get(key_path)

    def error(self, code: str, key_path: _yaml.KeyPath, message: str) -> None:
        field = ".".join(str(p) for p in key_path) or None
        self.issues.append(
            Issue(code=code, path=self.path, line=self.line(key_path), field=field, message=message)
        )

    def unknown_target(self, path: SchemaPath, target: str, registry: dict[str, Schema]) -> None:
        known = ", ".join(f"`{t}`" for t in sorted(registry)) or "none"
        field = ".".join(("properties", *path, "target"))
        self.issues.append(
            Issue(
                code="schema-unknown-target",
                path=self.path,
                line=self.target_lines.get(path, {}).get(target),
                field=field,
                message=(
                    f"`{field}` names type `{target}`, which no concept defines "
                    f"(known types: {known})"
                ),
            )
        )

    def relation_line(self, path: SchemaPath) -> int | None:
        return self.line(("properties", *path, "relation"))

    def unknown_relation(
        self, path: SchemaPath, relation: str, relations: dict[str, RelationDef]
    ) -> None:
        known = ", ".join(f"`{r}`" for r in sorted(relations)) or "none"
        field = ".".join(("properties", *path, "relation"))
        self.issues.append(
            Issue(
                code="relation-unknown",
                path=self.path,
                line=self.relation_line(path),
                field=field,
                message=(
                    f"`{field}` names relation `{relation}`, which no relation file in "
                    f"`.knott/relations/` defines (known relations: {known}); "
                    "the reference still works as a plain reference"
                ),
            )
        )

    def parse(self, abs_path: Path) -> Schema | None:
        try:
            text = abs_path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self.issues.append(
                Issue(code="schema-invalid-yaml", path=self.path, message=f"cannot read: {exc}")
            )
            return None
        self.file = parse_markdown(text, self.path)
        if self.file.error is not None:
            self.issues.append(
                Issue(
                    code="schema-invalid-yaml",
                    path=self.path,
                    line=self.file.error_line,
                    message=self.file.error,
                )
            )
            return None
        data = self.file.frontmatter
        if data is None:
            self.issues.append(
                Issue(
                    code="schema-invalid-yaml",
                    path=self.path,
                    line=1,
                    message=(
                        "a concept file needs YAML frontmatter: start the file with a `---` "
                        "line, then `name: <type>`, then a closing `---` line"
                    ),
                )
            )
            return None

        self._check_top_keys(data)
        type_name = self._check_name(data)
        description = self._optional_str(data, ("description",))
        kid_required = self._kid_required(data)
        properties = self._parse_properties(data.get("properties"))
        if type_name is None:
            return None
        return Schema(
            type=type_name,
            path=self.path,
            description=description,
            kid_required=kid_required,
            properties=properties,
            template=markdown_body(text),
        )

    def _check_top_keys(self, data: dict[str, Any]) -> None:
        for key in data:
            if key in _TOP_KEY_HINTS:
                self.error(
                    "schema-invalid-field",
                    (key,),
                    f"unknown key `{key}` in concept file: {_TOP_KEY_HINTS[key]}",
                )
            elif key not in _TOP_KEYS:
                self.error(
                    "schema-invalid-field",
                    (key,),
                    f"unknown key `{key}` in concept file; allowed keys: {', '.join(_TOP_KEYS)}",
                )

    def _check_name(self, data: dict[str, Any]) -> str | None:
        if data.get("name") is None:
            self.error("schema-invalid-field", ("name",), "missing required key `name`")
            return None
        value = data["name"]
        if not isinstance(value, str) or not TYPE_NAME.match(value):
            self.error(
                "schema-invalid-field",
                ("name",),
                f"concept name must match ^[a-z][a-z0-9_-]*$, got {show(value)}",
            )
            return None
        return value

    def _kid_required(self, data: dict[str, Any]) -> bool:
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
        raw = self.file.raws.get(key_path)
        if type(value) is bool and (raw is None or raw in BOOLEAN_SPELLINGS):
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
            # Only top-level properties share the frontmatter with `type` and `kid`.
            if name in _RESERVED_FIELDS and len(base) == 1:
                self.error(
                    "schema-invalid-field",
                    (*base, name),
                    f"a property cannot be named `{name}`; {_RESERVED_FIELDS[name]}",
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

    def _parse_properties(self, value: Any) -> dict[str, AttributeDef]:
        properties: dict[str, AttributeDef] = {}
        for name, definition in self._fields(("properties",), value):
            prop = self._parse_definition(definition, ("properties", name), name)
            if prop is not None:
                properties[name] = prop
        return properties

    def _parse_definition(
        self, definition: dict[Any, Any], base: _yaml.KeyPath, name: str | None
    ) -> AttributeDef | None:
        """Parse a property, an object field, or a list's `items` / map's `values` (no name).

        Returns None when anything inside is invalid; every problem is still reported.
        """
        raw_type = definition.get("type")
        kind_name = _kind_name(raw_type)
        self._check_definition_keys(definition, base, kind_name, nested=name is None)
        required = False
        if name is not None:
            required = self._required_flag(definition, (*base, "required"))
        description = self._optional_str(definition, (*base, "description"))
        label = f"property `{name}`" if len(base) == 2 else f"`{'.'.join(map(str, base))}`"
        if raw_type is None:
            self.error(
                "schema-invalid-field",
                base,
                f"{label} is missing `type` (one of: {_PROPERTY_TYPES})",
            )
            return None
        if kind_name is None:
            self.error(
                "schema-invalid-field",
                (*base, "type"),
                f"unknown property type {show(raw_type)}; expected one of: {_PROPERTY_TYPES}",
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
        if kind_name == REFERENCE_KIND:
            allowed.append("relation")
        if kind_name == FILE_KIND:
            allowed.append("accept")
        for key in definition:
            if key == "required" and nested:
                container = "list" if base[-1] == "items" else "map"
                self.error(
                    "schema-invalid-field",
                    (*base, "required"),
                    f"`required` is not allowed on `{base[-1]}`: an item or value can never "
                    f"be empty; put `required` on the {container} itself",
                )
            elif key == "relation":
                self._check_relation_placement(base, kind_name)
            elif key == "accept":
                self._check_accept_placement(base, kind_name)
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

    def _check_relation_placement(self, base: _yaml.KeyPath, kind_name: str | None) -> None:
        """`relation:` belongs on a reference shape only (spec 0006)."""
        if kind_name in ("list", "map"):
            inner = _NESTING_KEYS[kind_name]
            self.error(
                "schema-invalid-field",
                (*base, "relation"),
                f"`relation` is not allowed on a {kind_name}: put `relation:` on `{inner}`",
            )
        elif kind_name is not None and kind_name != REFERENCE_KIND:
            self.error(
                "schema-invalid-field",
                (*base, "relation"),
                f"`relation` is only allowed when `type` is reference, but `type` is {kind_name}",
            )

    def _check_accept_placement(self, base: _yaml.KeyPath, kind_name: str | None) -> None:
        """`accept:` belongs on a file shape only (spec 0008)."""
        if kind_name in ("list", "map"):
            inner = _NESTING_KEYS[kind_name]
            self.error(
                "schema-invalid-field",
                (*base, "accept"),
                f"`accept` is not allowed on a {kind_name}: put `accept:` on `{inner}`",
            )
        elif kind_name is not None and kind_name != FILE_KIND:
            self.error(
                "schema-invalid-field",
                (*base, "accept"),
                f"`accept` is only allowed when `type` is file, but `type` is {kind_name}",
            )

    def _parse_accept(self, value: Any, base: _yaml.KeyPath) -> tuple[str, ...] | None:
        """Parse `accept`: a non-empty list of unique lowercase extensions, without the dot."""
        if value is None:
            return ()
        if not isinstance(value, list) or not value:
            got = "an empty list" if value == [] else f"{kind(value)} {show(value)}"
            self.error(
                "schema-invalid-field",
                base,
                f"`accept` must be a non-empty list of file extensions, got {got}, "
                "e.g. accept: [mp3, wav]",
            )
            return None
        extensions: list[str] = []
        ok = True
        for index, item in enumerate(value):
            if not isinstance(item, str) or not _EXTENSION.match(item):
                message = (
                    f"`accept` item {index + 1} must be a lowercase extension without the dot "
                    f"(letters and digits), got {kind(item)} {show(item)}"
                )
                if isinstance(item, str) and _EXTENSION.match(item.lstrip(".").lower()):
                    message += f"; write `{item.lstrip('.').lower()}`"
                self.error("schema-invalid-field", (*base, index), message)
                ok = False
            elif item in extensions:
                self.error(
                    "schema-invalid-field",
                    (*base, index),
                    f"`accept` lists `{item}` twice; name each extension once",
                )
                ok = False
            else:
                extensions.append(item)
        return tuple(extensions) if ok else None

    def _parse_shape(
        self, kind_name: str, definition: dict[Any, Any], base: _yaml.KeyPath, label: str
    ) -> Shape | None:
        if kind_name == FILE_KIND:
            accept = self._parse_accept(definition.get("accept"), (*base, "accept"))
            return None if accept is None else FileShape(accept)
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
        if kind_name == REFERENCE_KIND:
            reference = self._parse_reference(inner, (*base, key))
            relation = self._relation_name(definition, base)
            if reference is None or relation is None:
                return reference
            return ReferenceShape(reference.targets, relation=relation)
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

    def _relation_name(self, definition: dict[Any, Any], base: _yaml.KeyPath) -> str | None:
        value = definition.get("relation")
        if value is None or isinstance(value, str):
            return value
        self.error(
            "schema-invalid-field",
            (*base, "relation"),
            f"`relation` must be a relation name, got {kind(value)} {show(value)}",
        )
        return None

    def _parse_reference(self, value: Any, base: _yaml.KeyPath) -> ReferenceShape | None:
        """Parse `target`: one type name, or a non-empty list of unique type names."""
        lines: dict[str, int | None] = {}
        if isinstance(value, str) and value:
            lines[value] = self.line(base)
        elif isinstance(value, list) and value:
            ok = True
            for index, item in enumerate(value):
                if not isinstance(item, str) or not item:
                    self.error(
                        "schema-invalid-field",
                        (*base, index),
                        f"`target` item {index + 1} must be a type name, "
                        f"got {kind(item)} {show(item)}",
                    )
                    ok = False
                elif item in lines:
                    self.error(
                        "schema-invalid-field",
                        (*base, index),
                        f"`target` lists type `{item}` twice; name each type once",
                    )
                    ok = False
                else:
                    lines[item] = self.line((*base, index))
            if not ok:
                return None
        else:
            got = "an empty list" if value == [] or value == "" else f"{kind(value)} {show(value)}"
            self.error(
                "schema-invalid-field",
                base,
                f"`target` must be a type name or a non-empty list of type names, got {got}, "
                "e.g. target: script or target: [episode, meeting]",
            )
            return None
        # `base` is ("properties", ..., "target"); key the lines by the path in between.
        self.target_lines[tuple(str(p) for p in base[1:-1])] = lines
        return ReferenceShape(tuple(lines))

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


def _kind_name(raw_type: Any) -> str | None:
    """The property kind named by a schema `type` value, or None if it names none."""
    if not isinstance(raw_type, str):
        return None
    kinds = {*COMPOUND_KINDS, REFERENCE_KIND, FILE_KIND, *(t.value for t in ScalarType)}
    return raw_type if raw_type in kinds else None
