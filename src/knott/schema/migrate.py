"""Convert legacy ``.knott/schemas/*.yaml`` schemas into concept-file text (decision 0010).

Pure functions only: reading files, writing files and removing the legacy folder
belong to ``knott migrate``.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from typing import Any

import yaml

from knott._values import kind, show
from knott.errors import MigrateError

LEGACY_TOP_KEYS = ("type", "description", "kid", "attributes", "relations")
LEGACY_RELATION_KEYS = ("target", "required", "description")
# Wide enough that PyYAML never wraps a description.
_WIDTH = 1_000_000


def convert_legacy(data: Any, list_fields: set[str]) -> str:
    """Return concept-file text (frontmatter only) for one legacy schema mapping.

    ``list_fields`` names the relations that some entity stores as a YAML list;
    those become ``list`` of ``reference``, every other relation a single
    ``reference``. Raises ``MigrateError`` for anything the converter can't map.
    """
    if not isinstance(data, dict):
        actual = "empty" if data is None else f"a {kind(data)}"
        raise MigrateError(f"schema file must be a YAML mapping, but it is {actual}")
    for key in data:
        if key not in LEGACY_TOP_KEYS:
            raise MigrateError(
                f"unknown key `{key}` in schema; allowed keys: {', '.join(LEGACY_TOP_KEYS)}"
            )
    name = data.get("type")
    if name is None:
        raise MigrateError("missing required key `type`")
    if not isinstance(name, str):
        raise MigrateError(f"`type` must be a string, got {kind(name)} {show(name)}")

    concept: dict[str, Any] = {"name": name}
    for key in ("description", "kid"):
        if data.get(key) is not None:
            concept[key] = data[key]

    properties: dict[str, Any] = {}
    for prop, definition in _section(data, "attributes").items():
        properties[prop] = copy.deepcopy(definition)
    for prop, definition in _section(data, "relations").items():
        if prop in properties:
            raise MigrateError(f"field `{prop}` is declared both as an attribute and as a relation")
        properties[prop] = _convert_relation(prop, definition, prop in list_fields)
    if properties:
        concept["properties"] = properties

    body = yaml.dump(
        concept,
        Dumper=_ConceptDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=_WIDTH,
    )
    return f"---\n{body}---\n"


def legacy_list_fields(
    schema_type: str, relation_names: Iterable[str], entities: Iterable[Mapping[str, Any]]
) -> set[str]:
    """Relation names that any entity of ``schema_type`` stores as a YAML list.

    ``entities`` are frontmatter mappings; entities of other types are ignored.
    """
    names = set(relation_names)
    found: set[str] = set()
    for frontmatter in entities:
        if frontmatter.get("type") != schema_type:
            continue
        found.update(n for n in names if isinstance(frontmatter.get(n), list))
    return found


def _section(data: dict[Any, Any], key: str) -> dict[str, dict[Any, Any]]:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MigrateError(
            f"`{key}` must be a mapping of field name to definition, got {kind(value)}"
        )
    for prop, definition in value.items():
        if not isinstance(prop, str):
            raise MigrateError(f"field name in `{key}` must be a string, got {show(prop)}")
        if not isinstance(definition, dict):
            raise MigrateError(
                f"definition of `{key}.{prop}` must be a mapping, got {kind(definition)}"
            )
    return value


def _convert_relation(prop: str, definition: dict[Any, Any], as_list: bool) -> dict[str, Any]:
    for key in definition:
        if key not in LEGACY_RELATION_KEYS:
            raise MigrateError(
                f"unknown key `{key}` in `relations.{prop}`; "
                f"allowed keys: {', '.join(LEGACY_RELATION_KEYS)}"
            )
    if "target" not in definition:
        raise MigrateError(f"relation `{prop}` is missing `target`")
    target = definition["target"]
    if as_list:
        result: dict[str, Any] = {"type": "list"}
        for key in ("required", "description"):
            if key in definition:
                result[key] = definition[key]
        result["items"] = {"type": "reference", "target": target}
        return result
    result = {"type": "reference", "target": target}
    for key in ("required", "description"):
        if key in definition:
            result[key] = definition[key]
    return result


class _ConceptDumper(yaml.SafeDumper):
    """Block style, indented sequences, folded ``>`` for multi-line strings."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, False)


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = ">" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_ConceptDumper.add_representer(str, _represent_str)
