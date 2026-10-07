"""Describing constructed YAML values in messages."""

from __future__ import annotations

import datetime as dt
from typing import Any

# Boolean spellings accepted as written; YAML 1.1 also reads yes/no/on/off as booleans.
BOOLEAN_SPELLINGS = frozenset({"true", "True", "TRUE", "false", "False", "FALSE"})


def kind(value: Any) -> str:
    """Human name for the YAML kind of a constructed value (exact types, no subclasses)."""
    if value is None:
        return "null"
    names: dict[type, str] = {
        bool: "boolean",
        int: "integer",
        float: "number",
        str: "string",
        dt.datetime: "datetime",
        dt.date: "date",
        list: "list",
        dict: "mapping",
    }
    return names.get(type(value), type(value).__name__)


_MAX_SHOWN = 80


def show(value: Any, raw: str | None = None) -> str:
    """Render a value in backticks, preferring its source text when known."""
    if raw is not None:
        return f"`{_truncate(raw)}`"
    if isinstance(value, list):
        return "`[]`" if not value else f"`[…]` ({len(value)} items)"
    if isinstance(value, dict):
        return "`{}`" if not value else f"`{{…}}` ({len(value)} keys)"
    if value is None:
        return "`null`"
    if type(value) is bool:
        return "`true`" if value else "`false`"
    if isinstance(value, dt.date):
        return f"`{value.isoformat()}`"
    return f"`{_truncate(str(value))}`"


def _truncate(text: str) -> str:
    return text if len(text) <= _MAX_SHOWN else text[: _MAX_SHOWN - 1] + "…"
