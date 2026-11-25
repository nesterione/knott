"""Loop files: ``.knott/loops/**/*.md`` (spec 0010)."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from knott import _yaml
from knott._values import kind, show
from knott.models import Issue
from knott.schema.models import (
    EnumShape,
    LoopDef,
    LoopNeedDef,
    LoopStageDef,
    RelationDef,
    Schema,
    iter_references,
)
from knott.schema.validator import closest_option
from knott.vault.discovery import LOOPS_DIR
from knott.vault.entity import MarkdownFile, markdown_body, parse_markdown

LOOP_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
_KEYS = ("name", "description", "type", "property", "stages")
_REQUIRED = ("type", "property", "stages")
_STAGE_KEYS = ("needs",)
_HEADING = re.compile(r"^##[ \t]+(.*?)[ \t]*$")


def discover_loop_files(root: Path) -> list[str]:
    """Vault-relative paths of every loop file, sorted."""
    loops_dir = root / LOOPS_DIR
    if not loops_dir.is_dir():
        return []
    return sorted(p.relative_to(root).as_posix() for p in loops_dir.rglob("*.md") if p.is_file())


def load_loops(
    root: Path,
    schemas: dict[str, Schema],
    relations: dict[str, RelationDef],
    issues: list[Issue],
) -> dict[str, LoopDef]:
    """Load every loop file, by name. Problems are appended to ``issues``.

    Run after concepts and relations are loaded: a loop names a type, one of its enum
    properties, and relations by their inverse.
    """
    loops: dict[str, LoopDef] = {}
    name_owner: dict[str, str] = {}
    followed: dict[tuple[str, str], LoopDef] = {}
    for rel_path in discover_loop_files(root):
        parser = _LoopParser(rel_path, issues)
        raw = parser.parse(root / rel_path)
        if raw is None:
            continue
        first = name_owner.get(raw.name)
        if first is not None:
            parser.error(
                ("name",),
                f"loop `{raw.name}` is defined twice: in `{first}` and in `{rel_path}`\n"
                "each loop must be defined by exactly one loop file",
                code="schema-duplicate-loop",
            )
            continue
        name_owner[raw.name] = rel_path
        loop = parser.resolve(raw, schemas, relations)
        if loop is None:
            continue
        other = followed.get((loop.type, loop.property))
        if other is not None:
            parser.error(
                ("property",),
                f"loops `{other.name}` (`{other.path}`) and `{loop.name}` (`{rel_path}`) both "
                f"follow `{loop.type}.{loop.property}`\n"
                "one property can be the stage of one loop",
                code="schema-duplicate-loop",
            )
            continue
        followed[(loop.type, loop.property)] = loop
        loops[loop.name] = loop
    return loops


@dataclass
class _RawNeed:
    key_path: _yaml.KeyPath
    property: str | None = None
    inverse: str | None = None
    types: list[tuple[_yaml.KeyPath, str]] = field(default_factory=list)


@dataclass
class _RawLoop:
    name: str
    description: str | None
    type: str
    property: str
    stages: list[tuple[str, list[_RawNeed]]]
    body: str | None


class _LoopParser:
    def __init__(self, rel_path: str, issues: list[Issue]) -> None:
        self.path = rel_path
        self.issues = issues
        self.file = MarkdownFile(path=rel_path)
        self.failed = False

    def error(
        self, key_path: _yaml.KeyPath, message: str, code: str = "schema-invalid-field"
    ) -> None:
        line = self.file.line_of(key_path) if key_path else 1
        named = [str(part) for part in key_path if isinstance(part, str)]
        key = named[0] if named else None
        if "needs" in named[1:]:
            key = "needs"
        self.issues.append(Issue(code=code, path=self.path, line=line, field=key, message=message))

    def fail(
        self, key_path: _yaml.KeyPath, message: str, code: str = "schema-invalid-field"
    ) -> None:
        """Report a problem that keeps the loop from loading."""
        self.failed = True
        self.error(key_path, message, code)

    # --- reading the file ---------------------------------------------------

    def parse(self, abs_path: Path) -> _RawLoop | None:
        def invalid_yaml(message: str, line: int | None = None) -> None:
            self.issues.append(
                Issue(code="schema-invalid-yaml", path=self.path, line=line, message=message)
            )

        try:
            text = abs_path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            invalid_yaml(f"cannot read: {exc}")
            return None
        self.file = parse_markdown(text, self.path)
        if self.file.error is not None:
            invalid_yaml(self.file.error, self.file.error_line)
            return None
        data = self.file.frontmatter
        if data is None:
            invalid_yaml(
                "a loop file needs YAML frontmatter: start the file with a `---` line, then "
                "`name`, `type`, `property` and `stages`, then a closing `---` line",
                1,
            )
            return None

        for key in data:
            if key not in _KEYS:
                message = f"unknown key `{key}` in loop file; allowed keys: {', '.join(_KEYS)}"
                close = difflib.get_close_matches(key, _KEYS, n=1)
                if close:
                    message += f"; did you mean `{close[0]}`?"
                self.error((key,), message)

        description = data.get("description")
        if description is not None and not isinstance(description, str):
            self.error(
                ("description",),
                f"expected a string, got {kind(description)} {show(description)}",
            )
            description = None

        name = data.get("name")
        if name is None:
            self.error((), "missing required key `name`")
            return None
        if not isinstance(name, str) or not LOOP_NAME.match(name):
            self.error(("name",), f"loop name must match ^[a-z][a-z0-9_-]*$, got {show(name)}")
            return None

        for key in _REQUIRED:
            if data.get(key) is None:
                self.fail((), f"missing required key `{key}`")
        type_name = self._string(data, "type")
        property_name = self._string(data, "property")
        stages = self._stages(data.get("stages"))
        if self.failed or type_name is None or property_name is None or stages is None:
            return None
        return _RawLoop(
            name=name,
            description=description,
            type=type_name,
            property=property_name,
            stages=stages,
            body=markdown_body(text),
        )

    def _string(self, data: dict[str, Any], key: str) -> str | None:
        value = data.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            self.fail((key,), f"`{key}` must be a name, got {kind(value)} {show(value)}")
            return None
        return value

    def _stages(self, value: Any) -> list[tuple[str, list[_RawNeed]]] | None:
        if value is None:
            return None
        base: _yaml.KeyPath = ("stages",)
        if type(value) is not dict or not value:
            self.fail(
                base,
                "`stages` must be a non-empty mapping of stage → nothing, or `{ needs: [...] }`, "
                f"got {kind(value)} {show(value)}",
            )
            return None
        stages: list[tuple[str, list[_RawNeed]]] = []
        for stage, body in value.items():
            if not isinstance(stage, str):
                self.fail(
                    base,
                    f"stage {show(stage)} is {_article(kind(stage))}, not a string; YAML reads "
                    f'it that way unquoted, so quote it: "{_as_written(stage)}"',
                )
                continue
            here = (*base, stage)
            needs: list[_RawNeed] = []
            if body is None:
                stages.append((stage, needs))
                continue
            if type(body) is not dict:
                self.fail(
                    here,
                    f"stage `{stage}` must be empty or `{{ needs: [...] }}`, "
                    f"got {kind(body)} {show(body)}",
                )
                continue
            for key in body:
                if key not in _STAGE_KEYS:
                    self.fail(
                        (*here, key) if isinstance(key, str) else here,
                        f"unknown key `{key}` in stage `{stage}`; the only key is `needs`",
                    )
            raw_needs = body.get("needs")
            if raw_needs is not None:
                needs = self._needs(raw_needs, (*here, "needs"), stage)
            stages.append((stage, needs))
        return stages

    def _needs(self, value: Any, base: _yaml.KeyPath, stage: str) -> list[_RawNeed]:
        if type(value) is not list or not value:
            self.fail(
                base,
                f"`needs` of stage `{stage}` must be a non-empty list, "
                f"got {kind(value)} {show(value)}",
            )
            return []
        needs: list[_RawNeed] = []
        for index, item in enumerate(value):
            here = (*base, index)
            if isinstance(item, str) and item.strip():
                needs.append(_RawNeed(key_path=here, property=item))
                continue
            if type(item) is dict and len(item) == 1:
                inverse, types = next(iter(item.items()))
                listed = types if type(types) is list else [types]
                if (
                    isinstance(inverse, str)
                    and listed
                    and all(isinstance(t, str) and t.strip() for t in listed)
                ):
                    need = _RawNeed(key_path=here, inverse=inverse)
                    for position, type_name in enumerate(listed):
                        where = (*here, inverse, position) if type(types) is list else here
                        need.types.append((where, type_name))
                    needs.append(need)
                    continue
            self.fail(
                here,
                "a need is a property name, or `<inverse>: <type>` (one type or a list), "
                f"got {kind(item)} {show(item)}",
            )
        return needs

    # --- checking against concepts and relations ----------------------------

    def resolve(
        self, raw: _RawLoop, schemas: dict[str, Schema], relations: dict[str, RelationDef]
    ) -> LoopDef | None:
        def invalid(key_path: _yaml.KeyPath, message: str) -> None:
            self.fail(key_path, message, code="loop-invalid-target")

        schema = schemas.get(raw.type)
        if schema is None:
            known = ", ".join(f"`{t}`" for t in sorted(schemas)) or "none"
            invalid(("type",), f"loop `{raw.name}` names type `{raw.type}`, but no concept "
                    f"defines it (known types: {known})")  # fmt: skip
            return None
        definition = schema.properties.get(raw.property)
        if definition is None:
            message = (
                f"loop `{raw.name}` follows `{raw.type}.{raw.property}`, but `{raw.type}` has "
                "no such top-level property"
            )
            close = difflib.get_close_matches(raw.property, list(schema.properties), n=1)
            if close:
                message += f"; did you mean `{close[0]}`?"
            invalid(("property",), message)
            return None
        shape = definition.shape
        if not isinstance(shape, EnumShape):
            invalid(
                ("property",),
                f"loop `{raw.name}` follows `{raw.type}.{raw.property}`, which is not an enum; "
                "a loop's stages are the options of an `enum` property",
            )
            return None

        options = shape.names
        listed = [stage for stage, _ in raw.stages]
        for stage in listed:
            if stage not in options:
                message = (
                    f"stage `{stage}` is not an option of `{raw.type}.{raw.property}`; "
                    f"options: {', '.join(f'`{o}`' for o in options)}"
                )
                suggestion = closest_option(stage, options)
                if suggestion is not None:
                    message += f"; did you mean `{suggestion}`?"
                invalid(("stages", stage), message)

        by_inverse = {
            r.inverse: r for r in sorted(relations.values(), key=lambda r: r.name, reverse=True)
        }
        stages: list[LoopStageDef] = []
        guidance = _split_guidance(raw.body, options)
        for stage, raw_needs in raw.stages:
            needs: list[LoopNeedDef] = []
            for need in raw_needs:
                if need.property is not None:
                    if need.property == raw.property:
                        invalid(
                            need.key_path,
                            f"`{need.property}` is the loop's own stage property; "
                            "it cannot be a need",
                        )
                    elif need.property not in schema.properties:
                        message = (
                            f"need `{need.property}` is not a top-level property of `{raw.type}`"
                        )
                        close = difflib.get_close_matches(
                            need.property, list(schema.properties), n=1
                        )
                        if close:
                            message += f"; did you mean `{close[0]}`?"
                        invalid(need.key_path, message)
                    else:
                        needs.append(LoopNeedDef(kind="property", property=need.property))
                    continue
                assert need.inverse is not None
                relation = by_inverse.get(need.inverse)
                if relation is None:
                    known = ", ".join(f"`{i}`" for i in sorted(i for i in by_inverse if i))
                    invalid(
                        need.key_path,
                        f"need `{need.inverse}` is not the `inverse` of any relation "
                        f"(known inverses: {known or 'none'})",
                    )
                    continue
                for where, type_name in need.types:
                    source = schemas.get(type_name)
                    if source is None:
                        invalid(where, f"need `{need.inverse}: {type_name}` names type "
                                f"`{type_name}`, but no concept defines it")  # fmt: skip
                    elif not _can_point(source, relation.name, raw.type):
                        invalid(
                            where,
                            f"need `{need.inverse}: {type_name}`: `{type_name}` has no reference "
                            f"that names relation `{relation.name}` and can target `{raw.type}`",
                        )
                    else:
                        needs.append(
                            LoopNeedDef(
                                kind="inverse",
                                inverse=need.inverse,
                                relation=relation.name,
                                type=type_name,
                            )
                        )
            stages.append(
                LoopStageDef(
                    name=stage, needs=tuple(dict.fromkeys(needs)), guidance=guidance.get(stage)
                )
            )
        if self.failed:
            return None
        return LoopDef(
            name=raw.name,
            description=raw.description,
            type=raw.type,
            property=raw.property,
            stages=tuple(stages),
            exits=tuple(
                LoopStageDef(name=option, guidance=guidance.get(option))
                for option in options
                if option not in listed
            ),
            guidance=guidance.get(None),
            path=self.path,
            lines={key: self.file.key_lines.get(key) for key in _KEYS},
        )


def _can_point(source: Schema, relation: str, target: str) -> bool:
    return any(
        shape.relation == relation and target in shape.targets
        for _, shape in iter_references(source)
    )


def _split_guidance(body: str | None, options: tuple[str, ...]) -> dict[str | None, str]:
    """The body by stage: a ``## <option>`` line starts that option's part; the text
    before the first one has the key None. Blank parts are left out."""
    parts: dict[str | None, list[str]] = {None: []}
    current: str | None = None
    for line in (body or "").split("\n"):
        heading = _HEADING.match(line)
        if heading is not None and heading[1] in options:
            current = heading[1]
            parts.setdefault(current, [])
            continue
        parts[current].append(line)
    joined = {key: "\n".join(lines).strip("\n") for key, lines in parts.items()}
    return {key: text for key, text in joined.items() if text.strip()}


def _article(noun: str) -> str:
    return f"an {noun}" if noun[:1] in "aeiou" else f"a {noun}"


def _as_written(value: Any) -> str:
    if type(value) is bool:
        return "yes" if value else "no"
    return str(value)
