"""`knott validate --fix`: give entities without a `kid` a new one.

This is the only place knott edits a user's Markdown file. The edit is one inserted
line; the rest of the file stays byte-for-byte the same, and the result is re-parsed
before it is written.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from knott.vault.entity import FRONTMATTER_DELIMITER, parse_markdown
from knott.vault.kid import KID_KEY

_BOM = "﻿"
_LINES = re.compile(r"(?<=\n)")


def insert_kid(vault_root: Path, rel_path: str, kid: str) -> bool:
    """Insert ``kid: <kid>`` into the frontmatter of ``rel_path``.

    The line goes after the top-level `type:` line, or else before the closing `---`.
    Returns False, writing nothing, when the file has a `kid` key already, is not an
    entity, resolves outside the vault, or neither position gives the same frontmatter
    plus the new `kid`.
    """
    path = vault_root / rel_path
    real = Path(os.path.realpath(path))
    if not real.is_relative_to(vault_root.resolve()):
        return False
    try:
        text = real.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    current = parse_markdown(text, rel_path)
    if current.error is not None or not current.is_entity:
        return False
    assert current.frontmatter is not None
    if KID_KEY in current.frontmatter:
        return False
    expected = {**current.frontmatter, KID_KEY: kid}

    bom = _BOM if text.startswith(_BOM) else ""
    lines = _LINES.split(text.removeprefix(bom))
    newline = "\r\n" if lines[0].endswith("\r\n") else "\n"
    closing = next(
        i for i, line in enumerate(lines) if i > 0 and line.rstrip("\r\n") == FRONTMATTER_DELIMITER
    )
    # key_lines are 1-based file lines; inserting at that index puts the line after `type:`.
    positions = [current.key_lines["type"], closing] if "type" in current.key_lines else [closing]
    for at in positions:
        candidate = bom + "".join([*lines[:at], f"{KID_KEY}: {kid}{newline}", *lines[at:]])
        reparsed = parse_markdown(candidate, rel_path)
        if reparsed.error is None and reparsed.frontmatter == expected:
            _write_atomic(real, candidate)
            return True
    return False


def _write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(text.encode("utf-8"))
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
