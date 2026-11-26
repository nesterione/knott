"""Concept discovery and parsing: ``.knott/concepts/**/*.md`` (decision 0010)."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from knott import _yaml
from knott._values import BOOLEAN_SPELLINGS, kind, show
from knott.models import Issue
from knott.schema.connectors import load_connectors
from knott.schema.filenames import FilenameDef, parse_filename
from knott.schema.loops import load_loops
from knott.schema.models import (
    ANY_TARGET,
    COMPOUND_KINDS,
    ENUM_KIND,
    FILE_KIND,
    REFERENCE_KIND,
    AttributeDef,
    ConnectorDef,
    EnumShape,
    FileShape,
    ListShape,
    LoopDef,
    MapShape,
    ObjectShape,
    ReferenceShape,
    RelationDef,
    ScalarType,
    Schema,
    SchemaPath,
    Shape,
)
from knott.schema.paths import normalize_pattern, pattern_problem
from knott.schema.relations import check_definitions, load_relations
from knott.vault.discovery import CONCEPTS_DIR, LEGACY_SCHEMAS_DIR
from knott.vault.entity import MarkdownFile, markdown_body, parse_markdown

TYPE_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")

_TOP_KEYS = (
    "name",
    "description",
    "extends",
    "abstract",
    "kid",
    "path",
    "filename",
    "properties",
)
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
    [*(t.value for t in ScalarType), *COMPOUND_KINDS, REFERENCE_KIND, FILE_KIND, ENUM_KIND]
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
    loops: dict[str, LoopDef] = field(default_factory=dict)
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

    _link_parents(registry, parsers)
    relations = load_relations(root, issues)
    for schema in registry.values():
        parser = parsers[schema.type]
        schema.own_properties = {
            name: _resolve_targets(definition, (name,), registry, relations, parser)
            for name, definition in schema.own_properties.items()
        }
    _inherit(registry, parsers)
    check_definitions(
        registry,
        relations,
        lambda schema, path: parsers[schema.type].relation_line(path),
        issues,
    )
    connectors = load_connectors(root, issues)
    loops = load_loops(root, registry, relations, issues)
    return Definitions(registry, relations, connectors, loops, issues)


def _link_parents(registry: dict[str, Schema], parsers: dict[str, _SchemaParser]) -> None:
    """Check every `extends` and set each concept's ancestors (spec 0013).

    An unknown parent and every concept in a cycle lose their parent; a concept
    below a cycle keeps its chain up to the first concept in it.
    """
    for schema in registry.values():
        parent = schema.extends
        if parent is not None and parent not in registry:
            known = ", ".join(f"`{t}`" for t in sorted(registry)) or "none"
            message = f"`extends` names type `{parent}`, which no concept defines"
            close = difflib.get_close_matches(parent, list(registry), n=1)
            if close:
                message += f"; did you mean `{close[0]}`?"
            parsers[schema.type].error(
                "schema-unknown-parent", ("extends",), f"{message} (known types: {known})"
            )
            schema.extends = None
    in_cycle: dict[str, list[str]] = {}
    for name in registry:
        chain = [name]
        current = registry[name].extends
        while current is not None and current not in chain:
            chain.append(current)
            current = registry[current].extends
        if current == name:
            in_cycle[name] = chain
    for name in sorted(in_cycle):
        cycle = " → ".join(f"`{t}`" for t in (*in_cycle[name], name))
        parsers[name].error(
            "schema-extends-cycle",
            ("extends",),
            f"`extends` forms a cycle: {cycle}\n"
            "a concept cannot be its own ancestor; remove one `extends`",
        )
    for name in in_cycle:
        registry[name].extends = None
    for schema in registry.values():
        ancestors: list[str] = []
        current = schema.extends
        while current is not None:
            ancestors.append(current)
            current = registry[current].extends
        schema.ancestors = tuple(ancestors)


def _inherit(registry: dict[str, Schema], parsers: dict[str, _SchemaParser]) -> None:
    """Give every concept what its ancestors declare (spec 0013): properties, root
    ancestor first, then the template, `path`, `filename` and `kid: required`."""
    for schema in registry.values():
        effective: dict[str, AttributeDef] = {}
        declared_in: dict[str, str] = {}
        for ancestor in reversed(schema.ancestors):
            for name, definition in registry[ancestor].own_properties.items():
                if name not in effective:
                    effective[name] = definition
                    declared_in[name] = ancestor
        own: dict[str, AttributeDef] = {}
        for name, definition in schema.own_properties.items():
            owner = declared_in.get(name)
            if owner is None:
                own[name] = definition
                continue
            parsers[schema.type].error(
                "schema-property-redefined",
                ("properties", name),
                f"property `{name}` is already declared by `{owner}` "
                f"(`{registry[owner].path}`), which `{schema.type}` extends\n"
                "a concept can only add properties; remove it here, or move it from "
                f"`{owner}` to the concepts that need it",
            )
        schema.own_properties = own
        schema.properties = {**effective, **own}
        schema.declared_in = declared_in
        for ancestor in schema.ancestors:
            parent = registry[ancestor]
            if schema.template is None and schema.template_from is None and parent.template:
                schema.template_from = ancestor
            if not schema.entity_paths and schema.entity_paths_from is None and parent.entity_paths:
                schema.entity_paths_from = ancestor
            if schema.filename is None and schema.filename_from is None and parent.filename:
                schema.filename_from = ancestor
            if not schema.kid_required and schema.kid_required_from is None and parent.kid_required:
                schema.kid_required_from = ancestor
    # Own values are read above; only now replace them with the inherited ones.
    for schema in registry.values():
        if schema.template_from is not None:
            schema.template = registry[schema.template_from].template
        if schema.entity_paths_from is not None:
            schema.entity_paths = registry[schema.entity_paths_from].entity_paths
        if schema.filename_from is not None:
            schema.filename = registry[schema.filename_from].filename
        if schema.kid_required_from is not None:
            schema.kid_required = True


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
        accepts = frozenset(
            s.type for s in registry.values() if any(s.is_a(target) for target in known)
        )
        new_shape = ReferenceShape(known, unknown, relation, shape.open, accepts)
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
        entity_paths = self._entity_paths(data)
        filename = self._filename(data)
        extends = self._extends(data)
        abstract = self._abstract(data)
        properties = self._parse_properties(data.get("properties"))
        if type_name is None:
            return None
        return Schema(
            type=type_name,
            path=self.path,
            description=description,
            kid_required=kid_required,
            entity_paths=entity_paths,
            filename=filename,
            properties=properties,
            own_properties=dict(properties),
            template=markdown_body(text),
            extends=extends,
            abstract=abstract,
        )

    def _extends(self, data: dict[str, Any]) -> str | None:
        value = data.get("extends")
        if value is None or isinstance(value, str):
            return value
        self.error(
            "schema-invalid-field",
            ("extends",),
            f"`extends` must be the name of one concept, got {kind(value)} {show(value)}",
        )
        return None

    def _abstract(self, data: dict[str, Any]) -> bool:
        value = data.get("abstract", False)
        if value is None:
            return False
        raw = self.file.raws.get(("abstract",))
        if type(value) is bool and (raw is None or raw in BOOLEAN_SPELLINGS):
            return value
        self.error(
            "schema-invalid-field",
            ("abstract",),
            f"`abstract` must be true or false, got {kind(value)} {show(value, raw)}",
        )
        return False

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
        if value == ANY_TARGET:
            self.error(
                "schema-invalid-field",
                ("name",),
                f"a concept cannot be named `{ANY_TARGET}`; it is reserved for "
                f"`target: {ANY_TARGET}`, a reference to any entity",
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

    def _entity_paths(self, data: dict[str, Any]) -> tuple[str, ...]:
        """The folder patterns of `path` (spec 0011); none when any of them is invalid."""
        value = data.get("path")
        if value is None:
            return ()
        if isinstance(value, str):
            items: list[tuple[_yaml.KeyPath, Any]] = [(("path",), value)]
        elif isinstance(value, list) and value:
            items = [(("path", i), item) for i, item in enumerate(value)]
        else:
            self.error(
                "schema-invalid-field",
                ("path",),
                "`path` must be a folder pattern or a non-empty list of them, "
                f"got {kind(value)} {show(value)}",
            )
            return ()
        patterns: list[str] = []
        valid = True
        for key_path, item in items:
            problem: str | None
            if not isinstance(item, str):
                problem = f"must be a string, got {kind(item)} {show(item)}"
            else:
                pattern = normalize_pattern(item)
                problem = pattern_problem(pattern)
                if problem is None and pattern in patterns:
                    problem = "is listed twice"
                if problem is None:
                    patterns.append(pattern)
            if problem is not None:
                valid = False
                self._path_error(key_path, f"`path` pattern {show(item)} {problem}")
        return tuple(patterns) if valid else ()

    def _filename(self, data: dict[str, Any]) -> FilenameDef | None:
        """The file-name pattern of `filename` (spec 0012); None when anything is invalid."""
        if data.get("filename") is None:
            return None

        def report(key_path: _yaml.KeyPath, message: str) -> None:
            line = next(
                (
                    found
                    for end in range(len(key_path), 0, -1)
                    if (found := self.line(key_path[:end])) is not None
                ),
                None,
            )
            self.issues.append(
                Issue(
                    code="schema-invalid-field",
                    path=self.path,
                    line=line,
                    field=".".join(str(p) for p in key_path),
                    message=message,
                )
            )

        return parse_filename(data["filename"], report)

    def _path_error(self, key_path: _yaml.KeyPath, message: str) -> None:
        line = self.line(key_path) or self.line(("path",))
        self.issues.append(
            Issue(
                code="schema-invalid-field",
                path=self.path,
                line=line,
                field="path",
                message=message,
            )
        )

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
        if kind_name == ENUM_KIND:
            allowed.append("options")
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
                self._check_owner(base, kind_name, "accept", FILE_KIND)
            elif key == "options":
                self._check_owner(base, kind_name, "options", ENUM_KIND)
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

    def _check_owner(
        self, base: _yaml.KeyPath, kind_name: str | None, key: str, owner: str
    ) -> None:
        """`accept:` belongs on a file shape only (spec 0008), `options:` on an enum (0009)."""
        if kind_name in ("list", "map"):
            inner = _NESTING_KEYS[kind_name]
            self.error(
                "schema-invalid-field",
                (*base, key),
                f"`{key}` is not allowed on a {kind_name}: put `{key}:` on `{inner}`",
            )
        elif kind_name is not None and kind_name != owner:
            self.error(
                "schema-invalid-field",
                (*base, key),
                f"`{key}` is only allowed when `type` is {owner}, but `type` is {kind_name}",
            )

    def _parse_options(
        self, value: Any, base: _yaml.KeyPath, label: str
    ) -> tuple[tuple[str, str | None], ...] | None:
        """Parse `options`: a list of strings, or a mapping of option → description."""
        if value is None:
            self.error(
                "schema-invalid-field",
                base[:-1],
                f"{label} has type enum but no `options`, e.g. options: [draft, published]",
            )
            return None
        if not isinstance(value, list | dict) or not value:
            got = (
                "an empty " + ("list" if value == [] else "mapping")
                if value in ([], {})
                else (f"{kind(value)} {show(value)}")
            )
            self.error(
                "schema-invalid-field",
                base,
                f"`options` must be a non-empty list of options, or a mapping of option to "
                f"description, got {got}, e.g. options: [draft, published]",
            )
            return None
        pairs = (
            [(index, item, None) for index, item in enumerate(value)]
            if isinstance(value, list)
            else [(key, key, description) for key, description in value.items()]
        )
        options: dict[str, str | None] = {}
        ok = True
        for where, option, description in pairs:
            at = (*base, where)
            if not isinstance(option, str):
                self._option_not_string(value, base, where, option)
                ok = False
            elif not option or option != option.strip():
                problem = "is empty" if not option else "has whitespace at its start or end"
                self.error("schema-invalid-field", at, f"option {show(option)} {problem}")
                ok = False
            elif option in options:
                self.error(
                    "schema-invalid-field",
                    at,
                    f"`options` lists `{option}` twice; name each option once",
                )
                ok = False
            elif description is not None and not isinstance(description, str):
                self.error(
                    "schema-invalid-field",
                    at,
                    f"the description of option `{option}` must be a string, "
                    f"got {kind(description)} {show(description)}",
                )
                ok = False
            else:
                options[option] = description or None
        return tuple(options.items()) if ok else None

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

    def _option_not_string(self, value: Any, base: _yaml.KeyPath, where: Any, option: Any) -> None:
        """Report an option YAML did not read as a string, with a hint to quote a scalar."""
        if isinstance(value, dict):
            # A non-string mapping key has no source position or spelling of its own.
            message = (
                f"an option must be a string, but YAML reads the key {show(option)} as "
                f"{kind(option)}; quote the key"
            )
            if type(option) is bool:
                message += " (YAML reads unquoted yes/no/on/off as booleans)"
            self.error("schema-invalid-field", base, message)
            return
        at = (*base, where)
        if isinstance(option, list | dict) or option is None:
            self.error(
                "schema-invalid-field",
                at,
                f"an option must be a string, got {kind(option)} {show(option)}",
            )
            return
        raw = self.file.raws.get(at)
        text = raw if raw is not None else show(option).strip("`")
        self.error(
            "schema-invalid-field",
            at,
            f"an option must be a string, but YAML reads {show(option, raw)} as "
            f'{kind(option)}; quote it, e.g. "{text}"',
        )

    def _parse_shape(
        self, kind_name: str, definition: dict[Any, Any], base: _yaml.KeyPath, label: str
    ) -> Shape | None:
        if kind_name == FILE_KIND:
            accept = self._parse_accept(definition.get("accept"), (*base, "accept"))
            return None if accept is None else FileShape(accept)
        if kind_name == ENUM_KIND:
            options = self._parse_options(definition.get("options"), (*base, "options"), label)
            return None if options is None else EnumShape(options)
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
            return ReferenceShape(reference.targets, relation=relation, open=reference.open)
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
        if value == ANY_TARGET:
            # An open reference (spec 0014): any entity, so there is no type to resolve.
            self.target_lines[tuple(str(p) for p in base[1:-1])] = lines
            return ReferenceShape((), open=True)
        if isinstance(value, str) and value:
            lines[value] = self.line(base)
        elif isinstance(value, list) and value:
            ok = True
            for index, item in enumerate(value):
                if item == ANY_TARGET:
                    # Reported, and the names beside it are kept and enforced.
                    self.error(
                        "schema-invalid-field",
                        base,
                        f"`{ANY_TARGET}` cannot be listed with other targets; write "
                        f"`target: {ANY_TARGET}` to accept every entity, or list only the types",
                    )
                elif not isinstance(item, str) or not item:
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
    kinds = {
        *COMPOUND_KINDS,
        REFERENCE_KIND,
        FILE_KIND,
        ENUM_KIND,
        *(t.value for t in ScalarType),
    }
    return raw_type if raw_type in kinds else None
