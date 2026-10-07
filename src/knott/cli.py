"""Command-line interface: a thin adapter over ``knott.api``."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from knott.api import Knott, version
from knott.errors import KnottError
from knott.models import Issue, ValidationResult

app = typer.Typer(
    name="knott",
    help="Knott: typed Markdown entities, schemas, and semantic relations.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

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
