"""Connector files: ``.knott/connectors/**/*.md`` (spec 0008)."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from knott._values import kind, show
from knott.models import Issue
from knott.schema.models import ConnectorDef
from knott.vault.discovery import CONNECTORS_DIR
from knott.vault.entity import MarkdownFile, markdown_body, parse_markdown

CONNECTOR_NAME = re.compile(r"^[a-z][a-z0-9+.-]*$")
"""A lowercase URI scheme."""
_KEYS = ("name", "description")
_RESERVED_NAMES = {"kid": "`kid:` names an entity in a reference"}


def discover_connector_files(root: Path) -> list[str]:
    """Vault-relative paths of every connector file, sorted."""
    connectors_dir = root / CONNECTORS_DIR
    if not connectors_dir.is_dir():
        return []
    return sorted(
        p.relative_to(root).as_posix() for p in connectors_dir.rglob("*.md") if p.is_file()
    )


def load_connectors(root: Path, issues: list[Issue]) -> dict[str, ConnectorDef]:
    """Load every connector file, by name. Problems are appended to ``issues``."""
    connectors: dict[str, ConnectorDef] = {}
    for rel_path in discover_connector_files(root):
        connector = _parse(root / rel_path, rel_path, issues)
        if connector is None:
            continue
        existing = connectors.get(connector.name)
        if existing is not None:
            issues.append(
                Issue(
                    code="schema-duplicate-connector",
                    path=rel_path,
                    line=connector.lines.get("name"),
                    field="name",
                    message=(
                        f"connector `{connector.name}` is defined twice: in `{existing.path}` "
                        f"and in `{rel_path}`\n"
                        "each connector must be defined by exactly one connector file"
                    ),
                )
            )
            continue
        connectors[connector.name] = connector
    return connectors


def _parse(abs_path: Path, rel_path: str, issues: list[Issue]) -> ConnectorDef | None:
    def invalid_yaml(message: str, line: int | None = None) -> None:
        issues.append(Issue(code="schema-invalid-yaml", path=rel_path, line=line, message=message))

    try:
        text = abs_path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        invalid_yaml(f"cannot read: {exc}")
        return None
    file: MarkdownFile = parse_markdown(text, rel_path)
    if file.error is not None:
        invalid_yaml(file.error, file.error_line)
        return None
    data = file.frontmatter
    if data is None:
        invalid_yaml(
            "a connector file needs YAML frontmatter: start the file with a `---` "
            "line, then `name: <scheme>`, then a closing `---` line",
            1,
        )
        return None

    def error(key: str, message: str) -> None:
        issues.append(
            Issue(
                code="schema-invalid-field",
                path=rel_path,
                line=file.key_lines.get(key),
                field=key,
                message=message,
            )
        )

    for key in data:
        if key not in _KEYS:
            message = f"unknown key `{key}` in connector file; allowed keys: {', '.join(_KEYS)}"
            close = difflib.get_close_matches(str(key), _KEYS, n=1)
            if close:
                message += f"; did you mean `{close[0]}`?"
            error(str(key), message)

    description = data.get("description")
    if description is not None and not isinstance(description, str):
        error("description", f"expected a string, got {kind(description)} {show(description)}")
        description = None

    name = data.get("name")
    if name is None:
        error("name", "missing required key `name`")
        return None
    if not isinstance(name, str) or not CONNECTOR_NAME.match(name):
        error(
            "name",
            "connector name must be a lowercase URI scheme matching ^[a-z][a-z0-9+.-]*$, "
            f"got {show(name)}",
        )
        return None
    if name in _RESERVED_NAMES:
        error("name", f"a connector cannot be named `{name}`: {_RESERVED_NAMES[name]}")
        return None
    return ConnectorDef(
        name=name,
        description=description,
        guidance=markdown_body(text),
        path=rel_path,
        lines={key: file.key_lines.get(key) for key in _KEYS},
    )
