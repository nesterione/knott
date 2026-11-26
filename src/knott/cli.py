"""Command-line interface: a thin adapter over ``knott.api``."""

from __future__ import annotations

import datetime as dt
import json
import os
import stat
import sys
import tempfile
import webbrowser
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import questionary
import typer
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent, merge_key_bindings

from knott.api import Knott, version
from knott.errors import KnottError
from knott.models import (
    ConnectorDefinition,
    EntityDetail,
    EntityRecord,
    FilenamePart,
    Issue,
    LoopDefinition,
    LoopReport,
    MigrateResult,
    MoveResult,
    Ontology,
    OntologyAttribute,
    OntologyType,
    RefGroup,
    Refs,
    RelationDefinition,
    ValidationResult,
    need_label,
    need_text,
)
from knott.skills import InstallResult, InstallStatus, SkillTarget, install_skill
from knott.view import render_ontology

app = typer.Typer(
    name="knott",
    help="Knott: typed Markdown entities, schemas, and semantic relations.",
    epilog=(
        "Agent skill: knott ships an Agent Skill for Claude Code, Codex and other agents. "
        "Install it into a project with `knott skill install`."
    ),
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

skill_app = typer.Typer(
    help=(
        "Manage the Agent Skill bundled with knott. The skill teaches AI agents how to read "
        "schemas, write entities and relations, and run `knott validate`. It installs to "
        ".claude/skills (Claude Code) and/or .agents/skills (Codex and other agents)."
    ),
    no_args_is_help=True,
)
app.add_typer(skill_app, name="skill", short_help="Install the knott Agent Skill for AI agents.")

EXIT_INVALID = 1
EXIT_USAGE = 2


class OutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


def _fail(error: KnottError) -> typer.Exit:
    typer.echo(f"error: {error}", err=True)
    return typer.Exit(EXIT_USAGE)


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def format_issue(issue: Issue) -> str:
    location = issue.path if issue.line is None else f"{issue.path}:{issue.line}"
    header = f"✗ {location}" + (f"  {issue.field}" if issue.field else "")
    body = "\n".join(f"  {line}" for line in issue.message.splitlines())
    return f"{header}\n{body}"


def format_type(t: OntologyType) -> str:
    """A type with its description, summary lines and properties (nested shapes indented)."""
    lines = [f"{t.type}  ({t.path})"]
    if t.description:
        lines += [f"  {line}" for line in t.description.strip().splitlines()]

    def origin(key: str) -> str:
        """`` (from <type>)`` for a setting an ancestor declares (spec 0013)."""
        return f" (from {t.inherited[key]})" if key in t.inherited else ""

    if t.extends is not None:
        lines.append(f"  extends: {t.extends}")
    if t.abstract:
        lines.append("  abstract: yes")
    if t.subtypes:
        lines.append(f"  subtypes: {', '.join(t.subtypes)}")
    if t.kid_required:
        lines.append(f"  kid: required{origin('kid')}")
    lines.append(f"  template: {'yes' if t.template is not None else 'no'}{origin('template')}")
    if t.entity_paths:
        lines.append(f"  path: {' | '.join(t.entity_paths)}{origin('path')}")
    if t.filename is not None:
        lines.append(f"  filename: {t.filename.pattern}.md{origin('filename')}")
        lines += _part_lines(t.filename.parts, "    ")
    paths = [path for path, _ in t.references()]
    lines.append(f"  references: {', '.join(paths) if paths else 'none'}")
    # One block per ancestor that declares properties, root first, then the type's own.
    for ancestor in reversed(t.ancestors):
        inherited = [a for a in t.properties if a.inherited_from == ancestor]
        if inherited:
            lines.append(f"  properties (from {ancestor}):")
            lines += _attribute_lines(inherited, "    ")
    own = [a for a in t.properties if a.inherited_from is None]
    if own:
        lines.append("  properties:")
        lines += _attribute_lines(own, "    ")
    return "\n".join(lines)


def format_selected_types(ontology: Ontology, names: list[str]) -> str:
    """Everything needed to write an entity of each named type (spec 0017): its
    `--verbose` block and body template, then only the relations, connectors and loops
    those types use. ``names`` are loaded types, without repeats."""
    by_name = {t.type: t for t in ontology.types}
    chosen = [by_name[name] for name in names]
    sections: list[str] = []
    for t in chosen:
        lines = [format_type(t)]
        if t.template is not None:
            lines.append("  template body:")
            lines += [f"    {line}" if line else "" for line in t.template.rstrip("\n").split("\n")]
        sections.append("\n".join(lines))
    # Relations named by a reference of a selected type, own or inherited, at any depth.
    named = {a.relation for t in chosen for _, a in t.references() if a.relation is not None}
    relations = [r for r in ontology.relations if r.name in named]
    if relations:
        sections.append(format_relations(relations))
    # A file property accepts any declared connector, so they are all listed.
    if ontology.connectors and any(_has_file(a) for t in chosen for a in t.properties):
        sections.append(format_connectors(ontology.connectors))
    followed = {name for t in chosen for name in (t.type, *t.ancestors)}
    loops = [loop for loop in ontology.loops if loop.type in followed]
    if loops:
        sections.append(format_loop_definitions(loops))
    return "\n\n".join(sections)


def _has_file(a: OntologyAttribute) -> bool:
    """Whether the attribute is a `file`, or holds one at any depth."""
    inner = [node for node in (a.items, a.values) if node is not None] + a.fields
    return a.type == "file" or any(_has_file(node) for node in inner)


def format_tree(types: list[OntologyType], *, verbose: bool = False) -> str:
    """The types as a tree, subtypes under their parent, with counts and folders (spec 0015).

    ``verbose`` adds each type's description and the properties it declares itself.
    """
    by_name = {t.type: t for t in types}
    children: dict[str | None, list[OntologyType]] = {}
    for t in sorted(types, key=lambda t: t.type):
        # a parent that did not load leaves the type a root
        children.setdefault(t.extends if t.extends in by_name else None, []).append(t)

    # (label, type, prefix of its detail lines), in print order
    rows: list[tuple[str, OntologyType, str]] = []

    def walk(parent: str | None, stem: str) -> None:
        siblings = children.get(parent, [])
        for i, t in enumerate(siblings):
            last = i == len(siblings) - 1
            name = t.type + (" (abstract)" if t.abstract else "")
            below = "" if parent is None else stem + ("   " if last else "│  ")
            connector = "" if parent is None else stem + ("└─ " if last else "├─ ")
            rows.append((connector + name, t, below + ("│  " if t.type in children else "   ")))
            walk(t.type, below)

    walk(None, "")
    label_width = max((len(label) for label, _, _ in rows), default=0)
    count_width = max((len(str(t.count)) for _, t, _ in rows if not t.abstract), default=0)
    lines: list[str] = []
    for label, t, detail in rows:
        count = "" if t.abstract else str(t.count)
        columns = [label.ljust(label_width), " | ".join(t.entity_paths)]
        if count_width:  # no count column when every type is abstract
            columns.insert(1, count.rjust(count_width))
        lines.append("  ".join(columns).rstrip())
        if not verbose:
            continue
        if t.description and t.description.strip():
            lines.append(detail + _one_line(t.description))
        own = [_label(a.name or "", a.required) for a in t.properties if a.inherited_from is None]
        if own:
            lines.append(f"{detail}adds: {', '.join(own)}")
    return "\n".join(lines)


def _part_lines(parts: list[FilenamePart], indent: str) -> list[str]:
    """One line per part of a file-name pattern: name, `match`, description, in columns."""
    if not parts:
        return []
    width = max(len(p.name) for p in parts)
    match_width = max(len(p.match or "") for p in parts)
    lines: list[str] = []
    for p in parts:
        line = f"{indent}{p.name:<{width}}  {p.match or '':<{match_width}}"
        if p.description:
            line += f"  {_one_line(p.description)}"
        lines.append(line.rstrip())
    return lines


def _notation(a: OntologyAttribute) -> str:
    """`OntologyAttribute.notation`, with targets no concept defines marked `(unknown)`."""
    inner = a.items or a.values
    if inner is not None:
        return f"{a.type} of {_notation(inner)}"
    if a.open:
        return f"{a.type} → any"
    targets = [*a.targets, *(f"{name} (unknown)" for name in a.unknown_targets)]
    if targets:
        return f"{a.type} → {' | '.join(targets)}"
    if a.accept:
        return f"{a.type} {' | '.join(f'.{e}' for e in a.accept)}"
    return a.type


def _type_column(a: OntologyAttribute) -> str:
    """The notation, then the relation the innermost reference names: ``(about)``."""
    node = a
    while (inner := node.items or node.values) is not None:
        node = inner
    return _notation(a) + (f"  ({node.relation})" if node.relation else "")


def _attribute_lines(attributes: list[OntologyAttribute], indent: str) -> list[str]:
    width = max(len(_label(a.name or "", a.required)) for a in attributes)
    type_width = max(len(_type_column(a)) for a in attributes)
    lines: list[str] = []
    for a in attributes:
        line = (
            f"{indent}{_label(a.name or '', a.required):<{width}}  {_type_column(a):<{type_width}}"
        )
        if a.description:
            line += f"  {_one_line(a.description)}"
        lines.append(line.rstrip())
        node = a
        while (inner := node.items or node.values) is not None:
            if inner.description:
                what = "each item" if node.items is not None else "each value"
                lines.append(f"{indent}  {what}: {_one_line(inner.description)}")
            node = inner
        lines += [f"{indent}  {line}" for line in _option_lines(node)]
        if node.fields:
            lines += _attribute_lines(node.fields, indent + "  ")
    return lines


def _option_lines(a: OntologyAttribute) -> list[str]:
    """An enum's options: one `one of:` line, or a line per option when any is described."""
    if not a.options:
        return []
    if not any(o.description for o in a.options):
        return ["one of: " + " | ".join(o.value for o in a.options)]
    return [
        f"{o.value}: {_one_line(o.description)}" if o.description else o.value for o in a.options
    ]


def format_relations(relations: list[RelationDefinition]) -> str:
    """The ``relations:`` section: per relation its name and keys on one line, then
    its description and guidance indented; relations separated by blank lines."""
    blocks: list[str] = []
    for r in relations:
        keys = [
            *([f"inverse: {r.inverse}"] if r.inverse is not None else []),
            *(["symmetric"] if r.symmetric else []),
            *(["acyclic"] if r.acyclic else []),
        ]
        lines = ["  ".join([f"  {r.name}", *keys])]
        for text in (r.description, r.guidance):
            if text and text.strip():
                lines += [f"    {line}".rstrip() for line in text.strip().splitlines()]
        blocks.append("\n".join(lines))
    return "relations:\n" + "\n\n".join(blocks)


def format_connectors(connectors: list[ConnectorDefinition]) -> str:
    """The ``connectors:`` section, in the format of the ``relations:`` section."""
    blocks: list[str] = []
    for c in connectors:
        lines = [f"  {c.name}"]
        for text in (c.description, c.guidance):
            if text and text.strip():
                lines += [f"    {line}".rstrip() for line in text.strip().splitlines()]
        blocks.append("\n".join(lines))
    return "connectors:\n" + "\n\n".join(blocks)


def format_loop_definitions(loops: list[LoopDefinition]) -> str:
    """The ``loops:`` section: per loop its name and property, then its description,
    path, side exits, each stage's needs and the guidance, indented."""
    blocks: list[str] = []
    for loop in loops:
        lines = [f"  {loop.name}  {loop.type}.{loop.property}"]
        if loop.description and loop.description.strip():
            lines += [f"    {line}".rstrip() for line in loop.description.strip().splitlines()]
        lines.append("    stages: " + " → ".join(s.name for s in loop.stages))
        if loop.exits:
            lines.append("    exits: " + " | ".join(s.name for s in loop.exits))
        for stage in loop.stages:
            if stage.needs:
                needs = ", ".join(need_label(n) for n in stage.needs)
                lines.append(f"    {stage.name} needs: {needs}")
        guidance = [loop.guidance] if loop.guidance else []
        guidance += [
            f"## {s.name}\n{s.guidance}" for s in [*loop.stages, *loop.exits] if s.guidance
        ]
        for text in guidance:
            lines += [f"    {line}".rstrip() for line in text.splitlines()]
        blocks.append("\n".join(lines))
    return "loops:\n" + "\n\n".join(blocks)


NO_STAGE = "no stage"


def format_loops(reports: list[LoopReport]) -> str:
    """One line per loop: name, ``type.property``, then entity counts per stage."""
    rows: list[tuple[str, str, str]] = []
    for report in reports:
        loop = report.loop
        counts = [f"{p.stage} {len(p.entities)}" for p in report.stages]
        if report.exits:
            exits = " · ".join(f"{p.stage} {len(p.entities)}" for p in report.exits)
            counts.append(f"({exits})")
        if report.unplaced:
            counts.append(f"{NO_STAGE} {len(report.unplaced)}")
        rows.append((loop.name, f"{loop.type}.{loop.property}", " · ".join(counts)))
    if not rows:
        return ""
    widths = [max(len(row[i]) for row in rows) for i in range(2)]
    return "\n".join(
        f"{name:<{widths[0]}}  {followed:<{widths[1]}}  {counts}" for name, followed, counts in rows
    )


def format_loop(report: LoopReport) -> str:
    """Each stage that has entities, then side exits, then ``no stage``; under each
    entity its unmet needs and what the next stage still misses."""
    blocks: list[str] = []
    for placement in report.stages:
        if not placement.entities:
            continue
        lines = [placement.stage]
        for entity in placement.entities:
            lines.append(f"  {entity.path}")
            lines += [f"    ✗ needs {need_text(need)}" for need in entity.unmet]
            if entity.next is not None:
                missing = ", ".join(need_label(need) for need in entity.missing_next)
                # Needs add up: an entity that fails its own stage is never ready.
                blocked = "after this stage's needs" if entity.unmet else "ready"
                state = f"missing {missing}" if missing else blocked
                lines.append(f"    next: {entity.next} — {state}")
        blocks.append("\n".join(lines))
    groups = [(p.stage, p.entities) for p in report.exits] + [(NO_STAGE, report.unplaced)]
    for label, entities in groups:
        if entities:
            blocks.append("\n".join([label, *(f"  {entity.path}" for entity in entities)]))
    return "\n".join(blocks)


def _label(name: str, required: bool) -> str:
    return name + ("*" if required else "")


def _one_line(text: str) -> str:
    return " ".join(text.split())


def format_result(result: ValidationResult) -> str:
    if result.ok:
        stats = result.stats
        return "\n".join(
            [
                f"✓ {_plural(stats.schemas, 'schema', 'schemas')}",
                f"✓ {_plural(stats.entities, 'entity', 'entities')}",
                f"✓ {_plural(stats.relations, 'relation', 'relations')}",
                "✓ vault is valid",
            ]
        )
    blocks = [format_issue(issue) for issue in result.issues]
    summary = _plural(len(result.issues), "validation error", "validation errors")
    return "\n\n".join([*blocks, summary])


@app.command()
def init(
    path: Annotated[
        Path, typer.Argument(help="Directory to initialize (default: current directory).")
    ] = Path("."),
) -> None:
    """Create .knott/concepts/ and .knott/config.yaml."""
    try:
        result = Knott.init(path)
    except KnottError as error:
        raise _fail(error) from None
    if result.created:
        typer.echo(f"Initialized Knott vault in {result.root}")
    else:
        typer.echo(f"Knott vault already initialized in {result.root}")


def format_migrate(result: MigrateResult) -> str:
    lines = [f"+ {path}" for path in result.written]
    lines += [f"  list of reference: {field}" for field in result.list_fields]
    lines.append(f"- {result.removed}/")
    return "\n".join(lines)


@app.command()
def migrate(
    path: Annotated[
        Path, typer.Argument(help="A path inside the vault (default: current directory).")
    ] = Path("."),
) -> None:
    """Convert a pre-0.5 vault's .knott/schemas/ into .knott/concepts/, then validate."""
    try:
        vault = Knott.open(path)
        migrated = vault.migrate()
        result = vault.validate()
    except KnottError as error:
        raise _fail(error) from None
    typer.echo(format_migrate(migrated))
    typer.echo()
    typer.echo(format_result(result))
    if not result.ok:
        raise typer.Exit(EXIT_INVALID)


@app.command()
def validate(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(help="Entity files or directories to check (default: the whole vault)."),
    ] = None,
    output: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.TEXT,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Add a `kid` to every checked entity that has none."),
    ] = False,
) -> None:
    """Validate schemas and entities."""
    try:
        start = paths[0] if paths else Path(".")
        vault = Knott.open(start if start.exists() else Path("."))
        result = vault.validate([p.absolute() for p in paths] if paths else None, fix=fix)
    except KnottError as error:
        raise _fail(error) from None
    if output is OutputFormat.JSON:
        payload: dict[str, object] = {
            "ok": result.ok,
            "stats": result.stats.model_dump(),
            "issues": [issue.model_dump() for issue in result.issues],
        }
        if fix:
            payload["fixed"] = [entity.model_dump() for entity in result.fixed]
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for entity in result.fixed:
            typer.echo(f"+ kid  {entity.path}")
        if result.fixed:
            typer.echo()
        typer.echo(format_result(result))
    if not result.ok:
        raise typer.Exit(EXIT_INVALID)


@app.command()
def types(
    names: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="[NAME]...",
            help=(
                "Types to show in full: the --verbose block, the body template, and the "
                "relations, connectors and loops they use (default: list every type)."
            ),
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help=(
                "Show each type's concept file, description, template, references and "
                "properties, then the relations, connectors and loops."
            ),
        ),
    ] = False,
    tree: Annotated[
        bool,
        typer.Option(
            "--tree",
            "-t",
            help=(
                "Show the types as a tree, subtypes under their parent, with entity counts "
                "and folders. With --verbose: each type's description and the properties it adds."
            ),
        ),
    ] = False,
) -> None:
    """List discovered entity types."""
    try:
        vault = Knott.open(".")
    except KnottError as error:
        raise _fail(error) from None
    if names and tree:
        raise _fail(KnottError("a type name cannot be combined with --tree"))
    if names:
        _fail_on_legacy(vault)
        ontology = vault.ontology()
        known = [t.type for t in ontology.types]
        for name in names:
            if name not in known:
                listed = ", ".join(f"`{t}`" for t in known) or "none"
                raise _fail(KnottError(f"no type named `{name}` (known types: {listed})"))
        typer.echo(format_selected_types(ontology, list(dict.fromkeys(names))))
    elif tree:
        output = format_tree(vault.ontology().types, verbose=verbose)
        if output:
            typer.echo(output)
    elif verbose:
        ontology = vault.ontology()
        sections = [format_type(t) for t in ontology.types]
        if ontology.relations:
            sections.append(format_relations(ontology.relations))
        if ontology.connectors:
            sections.append(format_connectors(ontology.connectors))
        if ontology.loops:
            sections.append(format_loop_definitions(ontology.loops))
        if sections:
            typer.echo("\n\n".join(sections))
    else:
        for info in vault.schemas():
            typer.echo(info.type)
    issues = vault.schema_issues()
    if issues:
        typer.echo("\n\n".join(format_issue(issue) for issue in issues), err=True)
        raise typer.Exit(EXIT_INVALID)


_DIRECTION_MARKS = {"in": "←", "out": "→", "both": "⇄"}


def format_refs(refs: Refs) -> str:
    """The entity's header line, then one block per group with aligned columns.

    Within a group, each column is padded to its widest value plus two spaces.
    """
    blocks = [f"{refs.entity.path}  {refs.entity.type}"]
    if not refs.groups:
        blocks.append("no references")
    return "\n\n".join(blocks + _group_blocks(refs.groups))


def _group_blocks(groups: list[RefGroup]) -> list[str]:
    """One block per reverse-lookup group: its label, then its references in columns."""
    blocks: list[str] = []
    for group in groups:
        rows = [
            [r.path, r.type, r.field]
            + ([_DIRECTION_MARKS[r.direction]] if group.kind == "symmetric" else [])
            for r in group.references
        ]
        widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
        lines = [group.label]
        for row in rows:
            cells = [f"{cell:<{width}}" for cell, width in zip(row, widths, strict=False)]
            lines.append("  " + "  ".join([*cells, row[-1]]))
        blocks.append("\n".join(lines))
    return blocks


def _columns(rows: list[list[str]], indent: str = "") -> list[str]:
    """Rows as lines, in columns padded to their widest value plus two spaces. A row's
    last cell is not padded, rows may differ in length, and no line ends in spaces."""
    widths: dict[int, int] = {}
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths.get(i, 0), len(cell))
    lines: list[str] = []
    for row in rows:
        cells = [f"{cell:<{widths[i]}}" for i, cell in enumerate(row[:-1])]
        lines.append((indent + "  ".join([*cells, row[-1]])).rstrip())
    return lines


def _cell(value: Any) -> str:
    """A frontmatter value on one line (spec 0016): a string as is, a number, boolean
    or date in its JSON form without quotes, a list or mapping as JSON, null as ``-``."""
    if value is None:
        return "-"
    if isinstance(value, str):
        return " ".join(value.splitlines())
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    return str(value)


def _json_default(value: Any) -> str:
    if isinstance(value, dt.date):
        return value.isoformat()
    raise TypeError(f"cannot write {type(value).__name__} as JSON")


def _dump(data: Any) -> str:
    """JSON output: dates in ISO 8601 form."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=_json_default, allow_nan=False)


def _record_data(record: EntityRecord) -> dict[str, Any]:
    """A record for JSON output: `properties` is left out when it was not asked for."""
    data: dict[str, Any] = {"path": record.path, "type": record.type, "kid": record.kid}
    if record.properties is not None:
        data["properties"] = record.properties
    return data


def format_entities(records: list[EntityRecord]) -> str:
    """One line per entity: path, type, then each chosen field."""
    if not records:
        return "no entities"
    rows = [
        [r.path, r.type, *(_cell(value) for value in (r.properties or {}).values())]
        for r in records
    ]
    return "\n".join(_columns(rows))


def format_entity(detail: EntityDetail, reference_keys: frozenset[str] = frozenset()) -> str:
    """The header line, then `properties`, `references`, `referenced by` and `body`,
    each left out when it has nothing. ``reference_keys`` are the top-level properties
    that hold only references: they are listed under `references`, not `properties`."""
    entity = detail.entity
    header = f"{entity.path}  {entity.type}" + (f"  kid:{entity.kid}" if entity.kid else "")
    blocks = [header]
    properties = [
        [name, _cell(value)]
        for name, value in (entity.properties or {}).items()
        if name not in reference_keys
    ]
    if properties:
        blocks.append("\n".join(["properties", *_columns(properties, "  ")]))
    rows: list[list[str]] = []
    for ref in detail.references:
        # An unresolved value shows as written, with the error where the type would be.
        row = [ref.field, ref.path if ref.path is not None else _cell(ref.value)]
        row.append(ref.type if ref.type is not None else ref.error or "")
        tail = [f"({ref.relation})"] if ref.relation is not None else []
        if ref.type is not None and ref.error is not None:
            tail.append(ref.error)
        rows.append(row + (["  ".join(tail)] if tail else []))
    if rows:
        blocks.append("\n".join(["references", *_columns(rows, "  ")]))
    if detail.referenced_by:
        groups = "\n\n".join(_group_blocks(detail.referenced_by))
        indented = [f"  {line}" if line else "" for line in groups.split("\n")]
        blocks.append("\n".join(["referenced by", *indented]))
    if detail.body is not None:
        blocks.append(f"body\n{detail.body}")
    return "\n\n".join(blocks)


def _fail_on_legacy(vault: Knott) -> None:
    """Exit 1 with the `schema-legacy-layout` issue when the vault has the legacy layout."""
    legacy = [i for i in vault.schema_issues() if i.code == "schema-legacy-layout"]
    if legacy:
        typer.echo("\n\n".join(format_issue(issue) for issue in legacy), err=True)
        raise typer.Exit(EXIT_INVALID)


@app.command("list")
def list_command(
    type_name: Annotated[
        str | None,
        typer.Argument(
            help="A type; its subtypes are included (default: every entity).", metavar="[TYPE]"
        ),
    ] = None,
    where: Annotated[
        list[str] | None,
        typer.Option(
            "--where",
            metavar="KEY=VALUE",
            help=(
                "Keep entities whose property KEY equals VALUE; repeat to combine. On a list, "
                "any item may match; for a reference, VALUE is an entity path or kid:<uuid>; "
                "an empty VALUE means the property is absent. Needs TYPE."
            ),
        ),
    ] = None,
    fields: Annotated[
        str | None,
        typer.Option(
            "--fields", metavar="KEY,...", help="Frontmatter keys to add to the output, in order."
        ),
    ] = None,
    output: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.TEXT,
) -> None:
    """List entities of a type, filtered by property values."""
    try:
        vault = Knott.open(".")
    except KnottError as error:
        raise _fail(error) from None
    _fail_on_legacy(vault)
    try:
        records = vault._entities_from_text(
            type_name,
            where or [],
            None if fields is None else [name.strip() for name in fields.split(",")],
            Path.cwd(),
        )
    except KnottError as error:
        raise _fail(error) from None
    if output is OutputFormat.JSON:
        typer.echo(_dump({"entities": [_record_data(r) for r in records]}))
    else:
        typer.echo(format_entities(records))


@app.command()
def show(
    path: Annotated[str, typer.Argument(help="An entity file, or kid:<uuid>.", metavar="PATH")],
    body: Annotated[bool, typer.Option("--body", help="Also print the body.")] = False,
    output: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.TEXT,
) -> None:
    """Show one entity: its properties, what it references and who references it."""
    is_kid = path.strip().startswith("kid:")
    try:
        vault = Knott.open("." if is_kid else path)
    except KnottError as error:
        raise _fail(error) from None
    _fail_on_legacy(vault)
    try:
        detail = vault.show(path if is_kid else Path(path).absolute(), body=body)
    except KnottError as error:
        raise _fail(error) from None
    if output is OutputFormat.JSON:
        data: dict[str, Any] = {
            "entity": _record_data(detail.entity),
            "references": [ref.model_dump() for ref in detail.references],
            "referenced_by": [group.model_dump() for group in detail.referenced_by],
        }
        if body:
            data["body"] = detail.body
        typer.echo(_dump(data))
    else:
        typer.echo(format_entity(detail, vault._reference_keys(detail.entity.type)))


def format_move(result: MoveResult) -> str:
    """What moved, then the rewritten links, then what was left alone (spec 0018)."""
    would = "would " if result.dry_run else ""
    moved = f"{would}move" if result.dry_run else "moved"
    blocks = [f"{moved} {result.from_} → {result.to}"]
    if result.updated:
        files = len({link.path for link in result.updated})
        head = (
            f"{would}update{'' if result.dry_run else 'd'} "
            f"{_plural(len(result.updated), 'link', 'links')} in {_plural(files, 'file', 'files')}"
        )
        rows = [[_at(u.path, u.line), u.field or "body"] for u in result.updated]
        blocks.append("\n".join([head, *_columns(rows, "  ")]))
    else:
        blocks.append("no links to update")
    if result.unchanged:
        rows = [[_at(u.path, u.line), u.field or "body", u.reason] for u in result.unchanged]
        head = f"unchanged {_plural(len(result.unchanged), 'link', 'links')}"
        blocks.append("\n".join([head, *_columns(rows, "  ")]))
    if result.skipped:
        rows = [[s.path, s.reason] for s in result.skipped]
        head = f"skipped {_plural(len(result.skipped), 'file', 'files')}"
        blocks.append("\n".join([head, *_columns(rows, "  ")]))
    return "\n\n".join(blocks)


def _at(path: str, line: int | None) -> str:
    return path if line is None else f"{path}:{line}"


@app.command()
def mv(
    source: Annotated[
        str, typer.Argument(help="A Markdown file in the vault, or kid:<uuid>.", metavar="SOURCE")
    ],
    dest: Annotated[
        Path, typer.Argument(help="The new path, or an existing folder.", metavar="DEST")
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would change; write nothing.")
    ] = False,
    output: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.TEXT,
) -> None:
    """Move or rename a file and rewrite the links to it."""
    is_kid = source.strip().startswith("kid:")
    try:
        vault = Knott.open("." if is_kid else source)
    except KnottError as error:
        raise _fail(error) from None
    _fail_on_legacy(vault)
    try:
        result = vault.move(
            source if is_kid else Path(source).absolute(), dest.absolute(), dry_run=dry_run
        )
    except KnottError as error:
        raise _fail(error) from None
    if output is OutputFormat.JSON:
        typer.echo(_dump(result.model_dump(mode="json", by_alias=True)))
    else:
        typer.echo(format_move(result))
    if result.issues:
        typer.echo("\n\n".join(format_issue(issue) for issue in result.issues), err=True)


@app.command()
def refs(
    path: Annotated[str, typer.Argument(help="An entity file, or kid:<uuid>.", metavar="PATH")],
    output: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.TEXT,
) -> None:
    """List who references an entity, grouped by relation."""
    is_kid = path.strip().startswith("kid:")
    try:
        vault = Knott.open("." if is_kid else path)
    except KnottError as error:
        raise _fail(error) from None
    _fail_on_legacy(vault)
    try:
        result = vault.refs(path if is_kid else Path(path).absolute())
    except KnottError as error:
        raise _fail(error) from None
    if output is OutputFormat.JSON:
        typer.echo(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        typer.echo(format_refs(result))


@app.command()
def loops(
    name: Annotated[
        str | None, typer.Argument(help="A loop's name (default: every loop).", metavar="[NAME]")
    ] = None,
    output: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.TEXT,
) -> None:
    """Show where entities stand in the vault's loops, and what each still needs."""
    try:
        vault = Knott.open(".")
        reports = vault.loops() if name is None else [vault.loops(name)]
    except KnottError as error:
        raise _fail(error) from None
    if output is OutputFormat.JSON:
        data = {"loops": [report.model_dump() for report in reports]}
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        text = format_loops(reports) if name is None else format_loop(reports[0])
        if text:
            typer.echo(text)
    issues = vault.schema_issues()
    if issues:
        typer.echo("\n\n".join(format_issue(issue) for issue in issues), err=True)
        raise typer.Exit(EXIT_INVALID)


@app.command()
def view(
    path: Annotated[
        Path, typer.Argument(help="A path inside the vault (default: current directory).")
    ] = Path("."),
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Write the page here (default: a file in the temp directory)."
        ),
    ] = None,
    no_open: Annotated[
        bool, typer.Option("--no-open", help="Write the page without opening a browser.")
    ] = False,
) -> None:
    """Draw the vault's ontology as an HTML page and open it in the browser."""
    try:
        vault = Knott.open(path)
        ontology = vault.ontology()
        loop_reports = vault.loops()
    except KnottError as error:
        raise _fail(error) from None
    legacy = [i for i in vault.schema_issues() if i.code == "schema-legacy-layout"]
    if legacy:
        # A pre-0.5 vault has no types to draw; say why instead of "no types".
        typer.echo("\n\n".join(format_issue(issue) for issue in legacy), err=True)
        raise typer.Exit(EXIT_INVALID)
    if not ontology.types:
        raise _fail(KnottError("no types to show (add concept files to .knott/concepts/)"))
    target = output or _private_temp_dir() / f"knott-ontology-{ontology.vault}.html"
    try:
        if output is None:
            _check_private(target.parent)
        target.write_text(render_ontology(ontology, loop_reports), encoding="utf-8")
    except OSError as error:
        raise _fail(KnottError(f"cannot write {target}: {error.strerror or error}")) from None
    typer.echo(f"Wrote {target}")
    if ontology.schema_issues:
        issues = _plural(ontology.schema_issues, "schema issue", "schema issues")
        typer.echo(f"{issues} — run knott validate", err=True)
    if not no_open and not webbrowser.open(target.resolve().as_uri()):
        typer.echo(f"could not open a browser; open {target}", err=True)


def _private_temp_dir() -> Path:
    """Per-user directory in the temp dir, so one page per vault is reused safely."""
    suffix = f"-{os.getuid()}" if hasattr(os, "getuid") else ""
    return Path(tempfile.gettempdir()) / f"knott{suffix}"


def _check_private(directory: Path) -> None:
    """Create ``directory`` (mode 0700) and refuse one another user could tamper with."""
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise OSError(f"{directory} is not a directory")
    if hasattr(os, "getuid") and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise OSError(f"{directory} is not private to the current user")


@app.command("version")
def version_command() -> None:
    """Print the installed Knott version."""
    typer.echo(version())


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _ask(question: questionary.Question) -> object:
    """Ask ``question``; Esc cancels like Ctrl-C and returns ``None``."""
    bindings = KeyBindings()

    @bindings.add("escape", eager=True)
    def _cancel(event: KeyPressEvent) -> None:
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    app = question.application
    app.key_bindings = merge_key_bindings([app.key_bindings or KeyBindings(), bindings])
    return question.ask()


def _choose_targets() -> list[SkillTarget]:
    choices = [
        questionary.Choice(
            f"{target.skills_dir}  ({label})", value=target, checked=target is SkillTarget.CLAUDE
        )
        for target, label in [
            (SkillTarget.CLAUDE, "Claude Code"),
            (SkillTarget.AGENTS, "Codex and other agents"),
        ]
    ]
    selected = _ask(
        questionary.checkbox(
            "Install the knott skill to:",
            choices=choices,
            instruction="(arrows to move, <space> to select, <enter> to confirm, <esc> to cancel)",
        )
    )
    return list(selected) if isinstance(selected, list) else []


def format_install(result: InstallResult, root: Path) -> str:
    location = result.path.relative_to(root).as_posix()
    if result.status is InstallStatus.CONFLICT:
        return f"✗ {location}  differs from bundled skill; rerun with --force to overwrite"
    message = {
        InstallStatus.CREATED: "installed",
        InstallStatus.UPDATED: "updated",
        InstallStatus.UNCHANGED: "up to date",
    }[result.status]
    return f"✓ {location}  {message}"


@skill_app.command("install")
def skill_install(
    path: Annotated[
        Path, typer.Argument(help="Project directory to install into (default: current directory).")
    ] = Path("."),
    claude: Annotated[
        bool, typer.Option("--claude", help="Install to .claude/skills (Claude Code).")
    ] = False,
    agents: Annotated[
        bool, typer.Option("--agents", help="Install to .agents/skills (Codex and other agents).")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an installed skill that differs.")
    ] = False,
) -> None:
    """Install the knott Agent Skill into a project.

    Without --claude or --agents, asks which targets to use (requires a terminal).
    """
    if not path.is_dir():
        raise _fail(KnottError(f"{path} is not a directory"))
    interactive = not (claude or agents)
    if interactive:
        if not _is_interactive():
            raise _fail(KnottError("no target given; pass --claude and/or --agents"))
        targets = _choose_targets()
        if not targets:
            typer.echo("Nothing installed.")
            raise typer.Exit(EXIT_INVALID)
    else:
        targets = [
            t
            for t, wanted in [(SkillTarget.CLAUDE, claude), (SkillTarget.AGENTS, agents)]
            if wanted
        ]
    conflicts = False
    for target in targets:
        try:
            result = install_skill(path, target, force=force)
            if result.status is InstallStatus.CONFLICT and interactive:
                location = result.path.relative_to(path).as_posix()
                question = f"{location} differs from the bundled skill. Overwrite?"
                if _ask(questionary.confirm(question, default=False)):
                    result = install_skill(path, target, force=True)
        except KnottError as error:
            raise _fail(error) from None
        typer.echo(format_install(result, path))
        conflicts = conflicts or result.status is InstallStatus.CONFLICT
    if conflicts:
        raise typer.Exit(EXIT_INVALID)
