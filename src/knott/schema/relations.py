"""Relation files: ``.knott/relations/**/*.md`` (spec 0006)."""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from knott._values import BOOLEAN_SPELLINGS, kind, show
from knott.models import Issue
from knott.schema.models import RelationDef, Schema, SchemaPath, iter_own_references
from knott.vault.discovery import RELATIONS_DIR
from knott.vault.entity import MarkdownFile, markdown_body, parse_markdown

RELATION_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
_KEYS = ("name", "description", "inverse", "symmetric", "acyclic")
_RESERVED_KEYS = {"transitive": "reserved, not supported yet"}


def discover_relation_files(root: Path) -> list[str]:
    """Vault-relative paths of every relation file, sorted."""
    relations_dir = root / RELATIONS_DIR
    if not relations_dir.is_dir():
        return []
    return sorted(
        p.relative_to(root).as_posix() for p in relations_dir.rglob("*.md") if p.is_file()
    )


def load_relations(root: Path, issues: list[Issue]) -> dict[str, RelationDef]:
    """Load every relation file, by name. Problems are appended to ``issues``."""
    relations: dict[str, RelationDef] = {}
    for rel_path in discover_relation_files(root):
        relation = _RelationParser(rel_path, issues).parse(root / rel_path)
        if relation is None:
            continue
        existing = relations.get(relation.name)
        if existing is not None:
            issues.append(
                Issue(
                    code="schema-duplicate-relation",
                    path=rel_path,
                    line=relation.lines.get("name"),
                    field="name",
                    message=(
                        f"relation `{relation.name}` is defined twice: in `{existing.path}` "
                        f"and in `{rel_path}`\n"
                        "each relation must be defined by exactly one relation file"
                    ),
                )
            )
            continue
        relations[relation.name] = relation
    return relations


def check_definitions(
    schemas: dict[str, Schema],
    relations: dict[str, RelationDef],
    relation_line: Callable[[Schema, SchemaPath], int | None],
    issues: list[Issue],
) -> None:
    """The checks on relation definitions (spec 0006, *Checks on definitions*).

    Run after every concept and relation file is loaded and every reference's
    targets and relation are resolved: only known targets are considered.
    """
    targets: dict[str, set[str]] = {}
    for schema in schemas.values():
        # Own properties only: an inherited one is checked once, where it is declared.
        for path, shape in iter_own_references(schema):
            if shape.relation is None:
                continue
            targets.setdefault(shape.relation, set()).update(shape.accepts or shape.targets)
            relation = relations[shape.relation]
            if (
                relation.symmetric
                and shape.targets
                and not any(schema.is_a(target) for target in shape.targets)
            ):
                field = ".".join(("properties", *path, "relation"))
                issues.append(
                    Issue(
                        code="relation-symmetric-mismatch",
                        path=schema.path,
                        line=relation_line(schema, path),
                        field=field,
                        message=(
                            f"`{field}` names symmetric relation `{relation.name}`, but its "
                            f"targets ({', '.join(f'`{t}`' for t in shape.targets)}) don't "
                            f"include its own concept `{schema.type}`\n"
                            "a symmetric link must be able to point back; add "
                            f"`{schema.type}` to `target` or name another relation"
                        ),
                    )
                )

    ordered = sorted(relations.values(), key=lambda r: r.path)
    first_inverse: dict[str, RelationDef] = {}
    for relation in ordered:
        inverse = relation.inverse
        line = relation.lines.get("inverse")

        def conflict(message: str, relation: RelationDef = relation) -> None:
            issues.append(_inverse_conflict(relation, message))

        if inverse is not None:
            other = first_inverse.get(inverse)
            if other is not None:
                conflict(
                    f"relations `{other.name}` (`{other.path}`) and `{relation.name}` "
                    f"(`{relation.path}`) both declare inverse `{inverse}`\n"
                    "each inverse name must belong to one relation"
                )
            else:
                first_inverse[inverse] = relation
            if inverse == relation.name:
                conflict(
                    f"relation `{relation.name}` declares itself as its own inverse; "
                    "use `symmetric: true` for a relation that reads the same both ways"
                )
            elif inverse in relations:
                conflict(
                    f"inverse `{inverse}` of relation `{relation.name}` is also the name of "
                    f"relation `{inverse}` (`{relations[inverse].path}`); choose another name"
                )
            # A property a target inherits is reported once, at the concept that declares it.
            declaring = {
                schemas[target].declared_in.get(inverse, target)
                for target in targets.get(relation.name, ())
                if inverse in schemas[target].properties
            }
            for target in sorted(declaring):
                if True:
                    conflict(
                        f"inverse `{inverse}` of relation `{relation.name}` is also a property "
                        f"of concept `{target}` (`{schemas[target].path}`), "
                        + (
                            "which this relation can point at"
                            if target in targets.get(relation.name, ())
                            else "inherited by a concept this relation can point at"
                        )
                        + "; reading the link from the target side would be ambiguous"
                    )
            if relation.symmetric:
                issues.append(
                    Issue(
                        code="relation-symmetric-mismatch",
                        path=relation.path,
                        line=line,
                        field="inverse",
                        message=(
                            f"relation `{relation.name}` is symmetric, so it reads the same "
                            "both ways and has no inverse; remove `inverse` or `symmetric`"
                        ),
                    )
                )
        if relation.symmetric and relation.acyclic:
            issues.append(
                Issue(
                    code="relation-symmetric-mismatch",
                    path=relation.path,
                    line=relation.lines.get("acyclic"),
                    field="acyclic",
                    message=(
                        f"relation `{relation.name}` is symmetric and acyclic, but every "
                        "symmetric link is a two-step cycle; remove `acyclic` or `symmetric`"
                    ),
                )
            )


class _RelationParser:
    def __init__(self, rel_path: str, issues: list[Issue]) -> None:
        self.path = rel_path
        self.issues = issues
        self.file = MarkdownFile(path=rel_path)

    def error(self, key: str | None, message: str, code: str = "schema-invalid-field") -> None:
        line = self.file.key_lines.get(key) if key is not None else None
        self.issues.append(Issue(code=code, path=self.path, line=line, field=key, message=message))

    def parse(self, abs_path: Path) -> RelationDef | None:
        try:
            text = abs_path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self.issues.append(
                Issue(code="schema-invalid-yaml", path=self.path, message=f"cannot read: {exc}")
            )
            return None
        self.file = parse_markdown(text, self.path)
        if self.file.error is not None:
            self.issues.append(
                Issue(
                    code="schema-invalid-yaml",
                    path=self.path,
                    line=self.file.error_line,
                    message=self.file.error,
                )
            )
            return None
        data = self.file.frontmatter
        if data is None:
            self.issues.append(
                Issue(
                    code="schema-invalid-yaml",
                    path=self.path,
                    line=1,
                    message=(
                        "a relation file needs YAML frontmatter: start the file with a `---` "
                        "line, then `name: <relation>`, then a closing `---` line"
                    ),
                )
            )
            return None

        for key in data:
            if key in _RESERVED_KEYS:
                self.error(key, f"`{key}` is {_RESERVED_KEYS[key]}; remove it")
            elif key not in _KEYS:
                message = f"unknown key `{key}` in relation file; allowed keys: {', '.join(_KEYS)}"
                close = difflib.get_close_matches(key, _KEYS, n=1)
                if close:
                    message += f"; did you mean `{close[0]}`?"
                self.error(key, message)
        name = self._name(data, "name")
        description = data.get("description")
        if description is not None and not isinstance(description, str):
            self.error(
                "description", f"expected a string, got {kind(description)} {show(description)}"
            )
            description = None
        inverse = self._name(data, "inverse") if data.get("inverse") is not None else None
        symmetric = self._flag(data, "symmetric")
        acyclic = self._flag(data, "acyclic")
        if name is None:
            return None
        return RelationDef(
            name=name,
            description=description,
            inverse=inverse,
            symmetric=symmetric,
            acyclic=acyclic,
            guidance=markdown_body(text),
            path=self.path,
            lines={key: self.file.key_lines.get(key) for key in _KEYS},
        )

    def _name(self, data: dict[str, Any], key: str) -> str | None:
        value = data.get(key)
        if value is None:
            self.error(key, f"missing required key `{key}`")
            return None
        if not isinstance(value, str) or not RELATION_NAME.match(value):
            self.error(key, f"relation {key} must match ^[a-z][a-z0-9_-]*$, got {show(value)}")
            return None
        return value

    def _flag(self, data: dict[str, Any], key: str) -> bool:
        value = data.get(key, False)
        if value is None:
            return False
        raw = self.file.raw.get(key)
        if type(value) is bool and (raw is None or raw in BOOLEAN_SPELLINGS):
            return value
        self.error(key, f"`{key}` must be true or false, got {kind(value)} {show(value, raw)}")
        return False


def _inverse_conflict(relation: RelationDef, message: str) -> Issue:
    return Issue(
        code="relation-inverse-conflict",
        path=relation.path,
        line=relation.lines.get("inverse"),
        field="inverse",
        message=message,
    )
