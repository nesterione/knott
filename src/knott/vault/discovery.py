"""Vault root lookup and Markdown file discovery."""

from __future__ import annotations

import os
from pathlib import Path

from knott.errors import VaultNotFoundError

KNOTT_DIR = ".knott"
CONCEPTS_DIR = f"{KNOTT_DIR}/concepts"
"""Concept files: one Markdown file per type (decision 0010)."""
RELATIONS_DIR = f"{KNOTT_DIR}/relations"
"""Relation files: one Markdown file per relation (spec 0006)."""
CONNECTORS_DIR = f"{KNOTT_DIR}/connectors"
"""Connector files: one Markdown file per URI scheme (spec 0008)."""
LOOPS_DIR = f"{KNOTT_DIR}/loops"
"""Loop files: one Markdown file per loop (spec 0010)."""
LEGACY_SCHEMAS_DIR = f"{KNOTT_DIR}/schemas"
"""The pre-0.5 schema folder; `knott migrate` converts it."""


def find_vault_root(start: Path) -> Path:
    """Return the nearest directory at or above ``start`` that contains ``.knott/``."""
    current = start.resolve()
    if not current.is_dir():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / KNOTT_DIR).is_dir():
            return candidate
    raise VaultNotFoundError(f"no Knott vault found at or above {start} (missing {KNOTT_DIR}/)")


def iter_markdown(root: Path) -> list[str]:
    """Vault-relative POSIX paths of all ``*.md`` files, sorted.

    Skips directories whose names start with ``.`` and does not follow
    symlinked directories.
    """
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        rel_dir = Path(dirpath).relative_to(root)
        for name in filenames:
            if name.endswith(".md") and (Path(dirpath) / name).is_file():
                found.append((rel_dir / name).as_posix())
    return sorted(found)
