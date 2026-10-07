"""Markdown file parsing: frontmatter detection and entity recognition."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from knott import _yaml

FRONTMATTER_DELIMITER = "---"
# YAML text starts on the second line of the file.
_YAML_LINE_OFFSET = 2
_LINE_BREAK = re.compile(r"\r?\n")


@dataclass(frozen=True)
class MarkdownFile:
    """A parsed Markdown file.

    Exactly one of these holds:
    - ``error`` is set: the file starts with ``---`` but the frontmatter is unusable.
    - ``frontmatter`` is a mapping (possibly without ``type``).
    - ``frontmatter`` is ``None``: no frontmatter, an ordinary note.
    """

    path: str
    frontmatter: dict[str, Any] | None = None
    key_lines: dict[str, int] = field(default_factory=dict)
    """1-based file line of each top-level frontmatter key."""
    item_lines: dict[tuple[str, int], int] = field(default_factory=dict)
    """1-based file line of each list item under a top-level key."""
    raw: dict[str, str] = field(default_factory=dict)
    """Source text of top-level scalar values."""
    error: str | None = None
    error_line: int | None = None

    @property
    def is_entity(self) -> bool:
        return self.frontmatter is not None and "type" in self.frontmatter

    @property
    def type(self) -> Any:
        return self.frontmatter.get("type") if self.frontmatter is not None else None


def read_markdown(abs_path: Path, rel_path: str) -> MarkdownFile:
    try:
        data = abs_path.read_bytes()
    except OSError as exc:
        return MarkdownFile(path=rel_path, error=f"cannot read file: {exc.strerror or exc}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        if data.removeprefix(b"\xef\xbb\xbf").startswith(b"---"):
            return MarkdownFile(path=rel_path, error="file is not valid UTF-8")
        return MarkdownFile(path=rel_path)
    return parse_markdown(text, rel_path)


def parse_markdown(text: str, rel_path: str) -> MarkdownFile:
    text = text.removeprefix("﻿")
    lines = _LINE_BREAK.split(text)
    if lines[0] != FRONTMATTER_DELIMITER:
        return MarkdownFile(path=rel_path)
    try:
        end = lines.index(FRONTMATTER_DELIMITER, 1)
    except ValueError:
        return MarkdownFile(
            path=rel_path,
            error="frontmatter starts with `---` on line 1 but has no closing `---` line",
            error_line=1,
        )
    yaml_text = "\n".join(lines[1:end])
    try:
        doc = _yaml.load(yaml_text)
    except _yaml.YamlParseError as exc:
        line = exc.line + _YAML_LINE_OFFSET if exc.line is not None else None
        return MarkdownFile(path=rel_path, error=exc.message, error_line=line)
    if not isinstance(doc.data, dict):
        actual = "empty" if doc.data is None else f"a {type(doc.data).__name__}"
        return MarkdownFile(
            path=rel_path,
            error=f"frontmatter must be a YAML mapping, but it is {actual}",
            error_line=1,
        )
    key_lines: dict[str, int] = {}
    item_lines: dict[tuple[str, int], int] = {}
    raw: dict[str, str] = {}
    for key_path, loc in doc.locs.items():
        if len(key_path) == 1 and isinstance(key_path[0], str):
            key_lines[key_path[0]] = loc.line + _YAML_LINE_OFFSET
            if loc.raw is not None:
                raw[key_path[0]] = loc.raw
        elif len(key_path) == 2 and isinstance(key_path[0], str) and isinstance(key_path[1], int):
            item_lines[(key_path[0], key_path[1])] = loc.line + _YAML_LINE_OFFSET
    # Non-string keys (e.g. an unquoted `yes:`) can never name a schema field.
    frontmatter = {k: v for k, v in doc.data.items() if isinstance(k, str)}
    return MarkdownFile(
        path=rel_path,
        frontmatter=frontmatter,
        key_lines=key_lines,
        item_lines=item_lines,
        raw=raw,
    )
