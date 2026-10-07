"""Command-line interface: a thin adapter over ``knott.api``."""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import questionary
import typer

from knott.api import Knott, version
from knott.errors import KnottError
from knott.models import Issue, ValidationResult
from knott.skills import InstallResult, InstallStatus, SkillTarget, install_skill

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
    """Create .knott/schemas/ and .knott/config.yaml."""
    try:
        result = Knott.init(path)
    except KnottError as error:
        raise _fail(error) from None
    if result.created:
        typer.echo(f"Initialized Knott vault in {result.root}")
    else:
        typer.echo(f"Knott vault already initialized in {result.root}")


@app.command()
def validate(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(help="Entity files or directories to check (default: the whole vault)."),
    ] = None,
    output: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.TEXT,
) -> None:
    """Validate schemas and entities."""
    try:
        start = paths[0] if paths else Path(".")
        vault = Knott.open(start if start.exists() else Path("."))
        result = vault.validate([p.absolute() for p in paths] if paths else None)
    except KnottError as error:
        raise _fail(error) from None
    if output is OutputFormat.JSON:
        payload = {
            "ok": result.ok,
            "stats": result.stats.model_dump(),
            "issues": [issue.model_dump() for issue in result.issues],
        }
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        typer.echo(format_result(result))
    if not result.ok:
        raise typer.Exit(EXIT_INVALID)


@app.command()
def types(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show each type's schema file and description.")
    ] = False,
) -> None:
    """List discovered entity types."""
    try:
        vault = Knott.open(".")
    except KnottError as error:
        raise _fail(error) from None
    for info in vault.schemas():
        if verbose:
            typer.echo(f"{info.type}  ({info.path})")
            if info.description:
                for line in info.description.strip().splitlines():
                    typer.echo(f"  {line}")
        else:
            typer.echo(info.type)
    issues = vault.schema_issues()
    if issues:
        typer.echo("\n\n".join(format_issue(issue) for issue in issues), err=True)
        raise typer.Exit(EXIT_INVALID)


@app.command("version")
def version_command() -> None:
    """Print the installed Knott version."""
    typer.echo(version())


def _is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


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
    selected = questionary.checkbox("Install the knott skill to:", choices=choices).ask()
    return list(selected or [])


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
                if questionary.confirm(question, default=False).ask():
                    result = install_skill(path, target, force=True)
        except KnottError as error:
            raise _fail(error) from None
        typer.echo(format_install(result, path))
        conflicts = conflicts or result.status is InstallStatus.CONFLICT
    if conflicts:
        raise typer.Exit(EXIT_INVALID)
