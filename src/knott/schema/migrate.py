"""Convert legacy ``.knott/schemas/*.yaml`` schemas into concept files (decision 0010).

``convert_legacy`` and ``legacy_list_fields`` are pure; ``migrate_vault`` reads the
legacy folder, writes the concept files and removes the folder.
"""

from __future__ import annotations

import contextlib
import copy
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from knott import _yaml
from knott._values import kind, show
from knott.errors import MigrateError
from knott.models import MigrateResult
from knott.vault.discovery import CONCEPTS_DIR, LEGACY_SCHEMAS_DIR, iter_markdown
from knott.vault.entity import read_markdown

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


@dataclass(frozen=True)
class _Planned:
    source: str
    target: Path
    target_rel: str
    text: str
    list_fields: list[str]


def migrate_vault(root: Path) -> MigrateResult:
    """Convert ``.knott/schemas/**/*.yaml`` under ``root`` into ``.knott/concepts/**/*.md``.

    Everything is read and converted first; any problem raises ``MigrateError``
    before a single file is written or removed. If writing a concept file fails
    (``OSError``), the files and folders written so far are removed again and
    ``MigrateError`` is raised, so the vault is left as it was. If only the final
    removal of ``.knott/schemas/`` fails, the concept files are complete and kept,
    and ``MigrateError`` asks the user to delete the legacy folder by hand: rolling
    back then could lose legacy files ``rmtree`` already deleted.
    """
    legacy = root / LEGACY_SCHEMAS_DIR
    if not legacy.is_dir():
        raise MigrateError(f"nothing to migrate: {root} has no `{LEGACY_SCHEMAS_DIR}/` folder")
    if legacy.is_symlink():
        raise MigrateError(
            f"`{LEGACY_SCHEMAS_DIR}/` is a symbolic link; replace it with a real folder "
            "first, since migrate deletes that folder"
        )
    sources: list[Path] = []
    for path in sorted(legacy.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if path.suffix == ".yaml":
            sources.append(path)
        elif not path.name.startswith("."):
            raise MigrateError(
                f"{rel}: not a `.yaml` schema; move it out of `{LEGACY_SCHEMAS_DIR}/` "
                "first, since migrate deletes that folder"
            )

    loaded = [(path, _read_legacy(root, path)) for path in sources]
    entities = _entity_frontmatters(root)

    planned: list[_Planned] = []
    for path, data in loaded:
        rel = path.relative_to(root).as_posix()
        relations = data.get("relations") if isinstance(data, dict) else None
        names = list(relations) if isinstance(relations, dict) else []
        schema_type = data.get("type") if isinstance(data, dict) else None
        found = (
            legacy_list_fields(schema_type, names, entities)
            if isinstance(schema_type, str)
            else set()
        )
        try:
            text = convert_legacy(data, found)
        except MigrateError as exc:
            raise MigrateError(f"{rel}: {exc}") from None
        target_rel = (
            PurePosixPath(CONCEPTS_DIR) / path.relative_to(legacy).with_suffix(".md").as_posix()
        ).as_posix()
        target = root / target_rel
        _check_parents(root, PurePosixPath(target_rel))
        if target.exists() or target.is_symlink():
            raise MigrateError(
                f"{target_rel} already exists; move it away or delete it, then run "
                "`knott migrate` again"
            )
        ordered = [n for n in names if n in found]
        planned.append(
            _Planned(rel, target, target_rel, text, [f"{schema_type}.{n}" for n in ordered])
        )

    _check_parents(root, PurePosixPath(CONCEPTS_DIR) / "_")
    _write_all(root, planned)
    try:
        shutil.rmtree(legacy)
    except OSError as exc:
        raise MigrateError(
            f"concept files written, but `{LEGACY_SCHEMAS_DIR}/` could not be removed: "
            f"{_reason(root, exc)}; delete `{LEGACY_SCHEMAS_DIR}/` by hand"
        ) from None
    return MigrateResult(
        written=[item.target_rel for item in planned],
        removed=LEGACY_SCHEMAS_DIR,
        list_fields=[field for item in planned for field in item.list_fields],
    )


def _check_parents(root: Path, target_rel: PurePosixPath) -> None:
    """Refuse when a folder on the way to ``target_rel`` exists but isn't a folder."""
    for parent in reversed(target_rel.parents[:-1]):
        path = root / parent
        if (path.exists() or path.is_symlink()) and not path.is_dir():
            raise MigrateError(
                f"{parent.as_posix()} is not a folder; move it away or delete it, then run "
                "`knott migrate` again"
            )


def _write_all(root: Path, planned: list[_Planned]) -> None:
    """Write every concept file; on ``OSError`` undo what was written and raise."""
    created: list[Path] = []
    written: list[Path] = []
    try:
        for item in planned:
            _make_dirs(item.target.parent, created)
            written.append(item.target)
            item.target.write_text(item.text, encoding="utf-8")
        _make_dirs(root / CONCEPTS_DIR, created)
    except OSError as exc:
        for path in written:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
        for path in reversed(created):
            with contextlib.suppress(OSError):
                path.rmdir()
        raise MigrateError(
            f"cannot write concept files: {_reason(root, exc)}; nothing was changed"
        ) from None


def _make_dirs(path: Path, created: list[Path]) -> None:
    """``mkdir -p`` that records, outermost first, each folder it creates."""
    missing = [p for p in (path, *path.parents) if not p.is_dir()]
    for folder in reversed(missing):
        folder.mkdir()
        created.append(folder)


def _reason(root: Path, exc: OSError) -> str:
    reason = exc.strerror or str(exc)
    if exc.filename is None:
        return reason
    name = Path(exc.filename)
    if name.is_relative_to(root):
        return f"{name.relative_to(root).as_posix()}: {reason}"
    return f"{name}: {reason}"


def _read_legacy(root: Path, path: Path) -> Any:
    rel = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise MigrateError(f"{rel}: file is not valid UTF-8") from None
    except OSError as exc:
        raise MigrateError(f"{rel}: cannot read file: {exc.strerror or exc}") from None
    try:
        return _yaml.load(text).data
    except _yaml.YamlParseError as exc:
        where = f"{rel}:{exc.line + 1}" if exc.line is not None else rel
        raise MigrateError(f"{where}: {exc.message}") from None


def _entity_frontmatters(root: Path) -> list[dict[str, Any]]:
    """Frontmatter of every readable entity; files with invalid frontmatter are skipped."""
    found: list[dict[str, Any]] = []
    for rel_path in iter_markdown(root):
        parsed = read_markdown(root / rel_path, rel_path)
        if parsed.error is None and parsed.is_entity and parsed.frontmatter is not None:
            found.append(parsed.frontmatter)
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
