"""Folder patterns of a concept's ``path`` key (spec 0011)."""

from __future__ import annotations

from pathlib import PurePosixPath

ROOT = "."
"""The vault root, as a pattern and as an entity's folder."""


def normalize_pattern(pattern: str) -> str:
    """``pattern`` without its one optional trailing ``/``."""
    return pattern[:-1] if len(pattern) > 1 and pattern.endswith("/") else pattern


def pattern_problem(pattern: str) -> str | None:
    """Why a normalized ``pattern`` is not a folder pattern, or None when it is one."""
    if pattern == "":
        return "is empty; write `.` for the vault root"
    if pattern == ROOT:
        return None
    if pattern.startswith("/"):
        return "starts with `/`; a pattern is relative to the vault root"
    if "\\" in pattern:
        return "contains `\\`; separate folders with `/`"
    for segment in pattern.split("/"):
        if segment == "":
            return "has an empty segment"
        if segment in (".", ".."):
            return f"has a `{segment}` segment; a pattern is relative to the vault root"
        if "**" in segment and segment != "**":
            return (
                f"uses `**` inside the segment `{segment}`; `**` must be a whole segment, "
                "and `*` matches inside one"
            )
    return None


def entity_folder(entity_path: str) -> str:
    """The vault-relative POSIX folder of an entity file; ``.`` for the root."""
    return PurePosixPath(entity_path).parent.as_posix()


def folder_matches(pattern: str, folder: str) -> bool:
    """Whether ``folder`` matches a valid, normalized ``pattern``. Case-sensitive."""
    wanted, names = _segments(pattern), _segments(folder)
    seen: dict[tuple[int, int], bool] = {}

    def match(p: int, f: int) -> bool:
        """Whether ``wanted[p:]`` matches ``names[f:]``; each pair is worked out once."""
        if p == len(wanted):
            return f == len(names)
        key = (p, f)
        if key not in seen:
            if wanted[p] == "**":
                seen[key] = any(match(p + 1, i) for i in range(f, len(names) + 1))
            else:
                seen[key] = (
                    f < len(names) and _segment_matches(wanted[p], names[f]) and match(p + 1, f + 1)
                )
        return seen[key]

    return match(0, 0)


def _segments(path: str) -> list[str]:
    return [] if path == ROOT else path.split("/")


def _segment_matches(pattern: str, name: str) -> bool:
    """``*`` is any run of characters, also none; everything else is literal."""
    parts = pattern.split("*")
    if len(parts) == 1:
        return pattern == name
    first, last = parts[0], parts[-1]
    if len(name) < len(first) + len(last) or not name.startswith(first):
        return False
    if last and not name.endswith(last):
        return False
    position, end = len(first), len(name) - len(last)
    for part in parts[1:-1]:
        found = name.find(part, position, end)
        if found < 0:
            return False
        position = found + len(part)
    return True
