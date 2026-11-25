"""Command-line interface: a thin adapter over ``knott.api``."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import webbrowser
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import questionary
import typer
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent, merge_key_bindings

from knott.api import Knott, version
from knott.errors import KnottError
from knott.models import (
    ConnectorDefinition,
    Issue,
    LoopDefinition,
    LoopReport,
    MigrateResult,
    OntologyAttribute,
    OntologyType,
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
    if t.kid_required:
        lines.append("  kid: required")
    lines.append(f"  template: {'yes' if t.template is not None else 'no'}")
    if t.entity_paths:
        lines.append(f"  path: {' | '.join(t.entity_paths)}")
    paths = [path for path, _ in t.references()]
    lines.append(f"  references: {', '.join(paths) if paths else 'none'}")
    if t.properties:
        lines.append("  properties:")
        lines += _attribute_lines(t.properties, "    ")
    return "\n".join(lines)


def _notation(a: OntologyAttribute) -> str:
    """`OntologyAttribute.notation`, with targets no concept defines marked `(unknown)`."""
    inner = a.items or a.values
    if inner is not None:
        return f"{a.type} of {_notation(inner)}"
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
) -> None:
    """List discovered entity types."""
    try:
        vault = Knott.open(".")
    except KnottError as error:
        raise _fail(error) from None
    if verbose:
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
    for group in refs.groups:
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
    return "\n\n".join(blocks)


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
    legacy = [i for i in vault.schema_issues() if i.code == "schema-legacy-layout"]
    if legacy:
        typer.echo("\n\n".join(format_issue(issue) for issue in legacy), err=True)
        raise typer.Exit(EXIT_INVALID)
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
