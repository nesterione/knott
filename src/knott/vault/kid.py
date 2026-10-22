"""The knott-managed entity identity: the `kid` frontmatter key and the vault-wide index."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, TypeGuard

from knott._values import kind, show
from knott.vault.entity import MarkdownFile

KID_KEY = "kid"
KID_EXAMPLE = "3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21"
_CANONICAL = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def is_canonical(value: Any) -> TypeGuard[str]:
    """True for a lowercase hyphenated UUID string (any version)."""
    return type(value) is str and _CANONICAL.match(value) is not None


def kid_problem(value: Any, raw: str | None = None) -> str:
    """Why ``value`` is not a valid `kid`, with the canonical form when there is one."""
    message = (
        f"must be a lowercase UUID such as {KID_EXAMPLE}, got {kind(value)} {show(value, raw)}"
    )
    if type(value) is str:
        try:
            canonical = str(uuid.UUID(value.strip()))
        except ValueError:
            return message
        message += f"; write {canonical}"
    return message


def new_kid() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class Claim:
    """An entity that declares a `kid`."""

    path: str
    line: int | None


KidIndex = dict[str, list[Claim]]
"""Valid `kid` -> the entities that declare it, in path order."""


def build_index(paths: Iterable[str], lookup: Callable[[str], MarkdownFile]) -> KidIndex:
    """Index the `kid` of every entity among ``paths``. Invalid values are not indexed."""
    index: KidIndex = {}
    for path in paths:
        parsed = lookup(path)
        if parsed.error is not None or not parsed.is_entity:
            continue
        assert parsed.frontmatter is not None
        value = parsed.frontmatter.get(KID_KEY)
        if is_canonical(value):
            index.setdefault(value, []).append(Claim(path, parsed.key_lines.get(KID_KEY)))
    return index


def format_claims(claims: list[Claim]) -> str:
    return ", ".join(f"{c.path}:{c.line}" if c.line is not None else c.path for c in claims)
