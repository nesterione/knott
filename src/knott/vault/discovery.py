"""Vault root lookup and Markdown file discovery."""

from __future__ import annotations

import os
from pathlib import Path

from knott.errors import VaultNotFoundError

KNOTT_DIR = ".knott"


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
