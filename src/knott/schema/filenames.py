"""File-name patterns of a concept's ``filename`` key (spec 0012)."""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from knott import _yaml
from knott._values import kind, show

PART_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
ENTITY_SUFFIX = ".md"

_KEYS = ("pattern", "parts")
_PART_KEYS = ("match", "description")

Report = Callable[[_yaml.KeyPath, str], None]
"""Records one ``schema-invalid-field`` at a key path below the concept's top level."""


@dataclass(frozen=True)
class FilenamePartDef:
    name: str
    match: str | None = None
    """A regular expression the part must match in full; None for any non-empty text."""
    description: str | None = None
    """How to fill the part, for whoever names the file. Never interpreted."""


@dataclass(frozen=True)
class FilenameDef:
    pattern: str
    """As written in the concept file, without ``.md``."""
    parts: tuple[FilenamePartDef, ...]
    """In the order the pattern uses them."""
    pieces: tuple[str | re.Pattern[str] | None, ...] = field(compare=False, repr=False)
    """The pattern in order: literal text, a part's compiled ``match``, or None for a
    part that is any non-empty text."""

    def matches(self, entity_path: str) -> bool:
        """Whether the whole name splits into the literal text and the parts, each part
        non-empty and matching its own expression in full."""
        name = entity_stem(entity_path)
        pieces = self.pieces
        failed: set[tuple[int, int]] = set()

        def fits(index: int, start: int) -> bool:
            if index == len(pieces):
                return start == len(name)
            if (index, start) in failed:
                return False
            piece = pieces[index]
            if isinstance(piece, str):
                found = name.startswith(piece, start) and fits(index + 1, start + len(piece))
            else:
                found = any(
                    (piece is None or piece.fullmatch(name[start:end]) is not None)
                    and fits(index + 1, end)
                    for end in self._ends(index, name, start)
                )
            if not found:
                failed.add((index, start))
            return found

        return fits(0, 0)

    def _ends(self, index: int, name: str, start: int) -> list[int]:
        """Where the part at ``index`` may end: only where the next piece can begin."""
        if index + 1 == len(self.pieces):
            return [len(name)] if len(name) > start else []
        following = self.pieces[index + 1]
        if not isinstance(following, str):
            return list(range(start + 1, len(name) + 1))
        ends: list[int] = []
        at = name.find(following, start + 1)
        while at >= 0:
            ends.append(at)
            at = name.find(following, at + 1)
        return ends

    @property
    def display(self) -> str:
        return self.pattern + ENTITY_SUFFIX

    @property
    def constraints(self) -> str:
        """``number: `[0-9]{4}`, slug: `…```: the parts that have a ``match``."""
        return ", ".join(f"{p.name}: `{p.match}`" for p in self.parts if p.match is not None)


def entity_stem(entity_path: str) -> str:
    """The file name without ``.md``, in Unicode NFC."""
    name = PurePosixPath(entity_path).name
    return unicodedata.normalize("NFC", name.removesuffix(ENTITY_SUFFIX))


def split_pattern(pattern: str) -> list[tuple[str, str]] | str:
    """``pattern`` as ``("text", literal)`` and ``("part", name)`` pieces, or the problem."""
    pieces: list[tuple[str, str]] = []
    seen: set[str] = set()
    position = 0
    while position < len(pattern):
        opening = pattern.find("{", position)
        literal = pattern[position:] if opening < 0 else pattern[position:opening]
        if "}" in literal:
            return "has a `}` with no `{` before it; a literal `{` or `}` cannot be written"
        for separator in ("/", "\\"):
            if separator in literal:
                return f"contains `{separator}`; a file name has no folders"
        if literal:
            pieces.append(("text", literal))
        if opening < 0:
            break
        closing = pattern.find("}", opening)
        if closing < 0:
            return "has a `{` that is never closed; a literal `{` or `}` cannot be written"
        name = pattern[opening + 1 : closing]
        if name == "":
            return "has an empty `{}`; write a part name such as `{slug}`"
        if not PART_NAME.match(name):
            return f"has the part `{{{name}}}`; a part name must match ^[a-z][a-z0-9_]*$"
        if name in seen:
            return f"uses the part `{{{name}}}` twice; a part may be used once"
        seen.add(name)
        pieces.append(("part", name))
        position = closing + 1
    return pieces


def match_problem(match: str) -> str | None:
    """Why ``match`` cannot be a part's expression, or None when it can."""
    try:
        compiled = re.compile(match)
    except (re.error, RecursionError, OverflowError) as exc:
        return f"is not a valid regular expression: {exc}"
    if compiled.fullmatch("") is not None:
        return "can match the empty string; a part is never empty"
    return None


def parse_filename(value: Any, report: Report) -> FilenameDef | None:
    """The definition under ``filename``, or None when anything in it is invalid."""
    if not isinstance(value, dict):
        report(
            ("filename",),
            f"`filename` must be a mapping with `pattern` and `parts`, got {kind(value)} "
            f"{show(value)}",
        )
        return None
    ok = True
    for key in value:
        if key not in _KEYS:
            ok = False
            message = f"unknown key `{key}` in `filename`; allowed keys: {', '.join(_KEYS)}"
            close = difflib.get_close_matches(str(key), _KEYS, n=1)
            if close:
                message += f"; did you mean `{close[0]}`?"
            report(("filename", key) if isinstance(key, str) else ("filename",), message)

    pattern = value.get("pattern")
    pieces: list[tuple[str, str]] = []
    if not isinstance(pattern, str) or pattern == "":
        ok = False
        got = "" if pattern is None else f", got {kind(pattern)} {show(pattern)}"
        if isinstance(pattern, dict | list):
            got += '; quote it, YAML reads a leading `{` as a mapping: `pattern: "{slug}"`'
        where: _yaml.KeyPath = ("filename", "pattern") if "pattern" in value else ("filename",)
        report(where, f"`filename` needs `pattern`, a non-empty string such as `{{slug}}`{got}")
    else:
        split = split_pattern(pattern)
        if isinstance(split, str):
            ok = False
            report(("filename", "pattern"), f"`pattern` {show(pattern)} {split}")
        else:
            pieces = split

    raw_parts = value.get("parts")
    if raw_parts is None:
        raw_parts = {}
    if not isinstance(raw_parts, dict):
        report(
            ("filename", "parts"),
            f"`parts` must be a mapping of part name → `match` and `description`, got "
            f"{kind(raw_parts)} {show(raw_parts)}",
        )
        return None
    parts: dict[str, FilenamePartDef] = {}
    for name, raw in raw_parts.items():
        part = _parse_part(name, raw, report)
        if part is None:
            ok = False
        else:
            parts[part.name] = part
    if not isinstance(pattern, str) or not pieces:
        return None

    used = [name for what, name in pieces if what == "part"]
    quotable = any(not isinstance(name, str) for name in raw_parts)
    for name in used:
        if name not in raw_parts and not quotable:
            ok = False
            report(
                ("filename", "pattern"),
                f"`pattern` uses the part `{{{name}}}`, which `parts` does not define; "
                f"add `{name}:` under `parts`",
            )
    for name in raw_parts:
        if isinstance(name, str) and PART_NAME.match(name) and name not in used:
            ok = False
            report(
                ("filename", "parts", name),
                f"`parts` defines `{name}`, which `pattern` does not use",
            )
    if not ok:
        return None

    compiled: list[str | re.Pattern[str] | None] = []
    for what, text in pieces:
        if what == "text":
            compiled.append(unicodedata.normalize("NFC", text))
        else:
            match = parts[text].match
            compiled.append(None if match is None else re.compile(match))
    return FilenameDef(
        pattern=pattern, parts=tuple(parts[name] for name in used), pieces=tuple(compiled)
    )


def _parse_part(name: Any, raw: Any, report: Report) -> FilenamePartDef | None:
    if not isinstance(name, str) or not PART_NAME.match(name):
        hint = "" if isinstance(name, str) else '; quote a name YAML reads otherwise: `"no":`'
        report(
            ("filename", "parts"),
            f"part name must match ^[a-z][a-z0-9_]*$, got {kind(name)} {show(name)}{hint}",
        )
        return None
    here: _yaml.KeyPath = ("filename", "parts", name)
    if raw is None:
        return FilenamePartDef(name=name)
    if not isinstance(raw, dict):
        report(
            here,
            f"part `{name}` must be empty or a mapping with `match` and `description`, got "
            f"{kind(raw)} {show(raw)}",
        )
        return None
    ok = True
    for key in raw:
        if key not in _PART_KEYS:
            ok = False
            message = f"unknown key `{key}` in part `{name}`; allowed keys: {', '.join(_PART_KEYS)}"
            close = difflib.get_close_matches(str(key), _PART_KEYS, n=1)
            if close:
                message += f"; did you mean `{close[0]}`?"
            report((*here, key) if isinstance(key, str) else here, message)
    match = raw.get("match")
    if match is not None:
        if not isinstance(match, str):
            ok = False
            report(
                (*here, "match"),
                f"`match` must be a string, got {kind(match)} {show(match)}; quote it",
            )
        elif (problem := match_problem(match)) is not None:
            ok = False
            report((*here, "match"), f"`match` {show(match)} {problem}")
    description = raw.get("description")
    if description is not None and not isinstance(description, str):
        ok = False
        report(
            (*here, "description"),
            f"expected a string, got {kind(description)} {show(description)}",
        )
    if not ok:
        return None
    return FilenamePartDef(name=name, match=match, description=description)
