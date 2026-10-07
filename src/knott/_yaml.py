"""Safe YAML loading that also records source line numbers.

Internal module: PyYAML nodes never leave it. Callers get plain Python data
plus a map from key paths to line numbers and raw scalar text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

KeyPath = tuple[str | int, ...]

# Upper bound on nodes after alias expansion. Real frontmatter and schemas are
# tiny; this only stops alias bombs (including via `<<` merge keys).
MAX_EXPANDED_NODES = 100_000
_STR_TAG = "tag:yaml.org,2002:str"

_MARKDOWN_LINK_LINE = re.compile(r"\[[^\]]*\]\([^)]*\)")


@dataclass(frozen=True)
class Loc:
    """Where a value sits in its source text.

    ``line`` is 0-based within the parsed YAML text: the line of the mapping key
    for mapping entries, or of the item itself for sequence items.
    ``raw`` is the scalar's source text, when the value is a scalar.
    """

    line: int
    raw: str | None


@dataclass(frozen=True)
class YamlDocument:
    data: Any
    locs: dict[KeyPath, Loc]


class YamlParseError(Exception):
    def __init__(self, message: str, line: int | None) -> None:
        super().__init__(message)
        self.message = message
        self.line = line  # 0-based within the parsed text, when known


def load(text: str) -> YamlDocument:
    """Parse one YAML document with ``SafeLoader``. Raises ``YamlParseError``."""
    try:
        loader = yaml.SafeLoader(text)
    except yaml.reader.ReaderError as exc:
        reader_line = text.count("\n", 0, exc.position)
        raise YamlParseError(f"invalid YAML: {exc.reason}", reader_line) from exc
    try:
        node = loader.get_single_node()
        if node is not None:
            _check_expansion(node)
        data = loader.construct_document(node) if node is not None else None
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        line = mark.line if mark is not None else None
        raise YamlParseError(_describe(exc, text, line), line) from exc
    except yaml.YAMLError as exc:
        raise YamlParseError(str(exc), None) from exc
    except ValueError as exc:  # e.g. an impossible date such as 2026-13-45
        raise YamlParseError(f"invalid value: {exc}", None) from exc
    except RecursionError:
        raise YamlParseError("invalid YAML: nesting is too deep", None) from None
    except YamlParseError:
        raise
    except Exception as exc:  # PyYAML constructors can fail oddly, e.g. `!!bool nope`
        raise YamlParseError(f"invalid YAML value: {exc!r}", None) from exc
    finally:
        loader.dispose()
    locs: dict[KeyPath, Loc] = {}
    if node is not None:
        try:
            _collect(node, (), locs)
        except RecursionError:
            raise YamlParseError("invalid YAML: nesting is too deep", None) from None
    return YamlDocument(data=data, locs=locs)


def _describe(exc: yaml.MarkedYAMLError, text: str, line: int | None) -> str:
    parts = [p for p in (exc.context, exc.problem) if p]
    message = "invalid YAML: " + ", ".join(parts) if parts else "invalid YAML"
    lines = text.split("\n")
    candidates = [line, line - 1] if line is not None else []
    for candidate in candidates:
        if 0 <= candidate < len(lines) and _MARKDOWN_LINK_LINE.search(lines[candidate]):
            message += '; a Markdown link must be quoted in YAML, e.g. key: "[label](path.md)"'
            break
    return message


def _check_expansion(root: yaml.Node) -> None:
    """Reject documents whose alias expansion would be huge or recursive."""
    sizes: dict[int, int] = {}
    in_progress: set[int] = set()

    def size(node: yaml.Node) -> int:
        key = id(node)
        if key in sizes:
            return sizes[key]
        if key in in_progress:
            raise YamlParseError("invalid YAML: recursive alias", node.start_mark.line)
        in_progress.add(key)
        total = 1
        if isinstance(node, yaml.MappingNode):
            for key_node, value_node in node.value:
                total += size(key_node) + size(value_node)
                if total > MAX_EXPANDED_NODES:
                    break
        elif isinstance(node, yaml.SequenceNode):
            for item in node.value:
                total += size(item)
                if total > MAX_EXPANDED_NODES:
                    break
        in_progress.discard(key)
        if total > MAX_EXPANDED_NODES:
            raise YamlParseError(
                "invalid YAML: aliases expand to too many values", node.start_mark.line
            )
        sizes[key] = total
        return total

    size(root)


def _collect(node: yaml.Node, path: KeyPath, locs: dict[KeyPath, Loc]) -> None:
    # Walks aliased nodes once per path, so aliased fields get full metadata.
    # Safe because _check_expansion already bounded the expanded size.
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            # Only string keys: a boolean `true:` must not share locs with `"true":`.
            if not isinstance(key_node, yaml.ScalarNode) or key_node.tag != _STR_TAG:
                continue
            child = (*path, key_node.value)
            raw = value_node.value if isinstance(value_node, yaml.ScalarNode) else None
            locs[child] = Loc(key_node.start_mark.line, raw)
            _collect(value_node, child, locs)
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            child = (*path, index)
            raw = item.value if isinstance(item, yaml.ScalarNode) else None
            locs[child] = Loc(item.start_mark.line, raw)
            _collect(item, child, locs)
