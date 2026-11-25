"""Loops: where each entity stands, and what its stage needs (spec 0010)."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from pathlib import PurePosixPath

from knott.models import (
    Issue,
    LoopDefinition,
    LoopEntity,
    LoopNeed,
    LoopPlacement,
    LoopReport,
    LoopStage,
)
from knott.schema.models import LoopDef, LoopNeedDef, LoopStageDef, ScalarType, Schema
from knott.schema.validator import is_empty
from knott.vault.entity import MarkdownFile
from knott.vault.index import VaultSession
from knott.vault.refs import entity_kid

TITLE_KEY = "title"


def loop_definition(loop: LoopDef) -> LoopDefinition:
    return LoopDefinition(
        name=loop.name,
        description=loop.description,
        type=loop.type,
        property=loop.property,
        stages=[_stage(s) for s in loop.stages],
        exits=[_stage(s) for s in loop.exits],
        guidance=loop.guidance,
        path=loop.path,
    )


def _stage(stage: LoopStageDef) -> LoopStage:
    return LoopStage(
        name=stage.name,
        needs=[_need(n, stage.name) for n in stage.needs],
        guidance=stage.guidance,
    )


def _need(need: LoopNeedDef, since: str) -> LoopNeed:
    return LoopNeed(
        kind="property" if need.kind == "property" else "inverse",
        property=need.property,
        inverse=need.inverse,
        relation=need.relation,
        type=need.type,
        since=since,
    )


def loop_report(session: VaultSession, loop: LoopDef) -> LoopReport:
    """Place every entity of the loop's type by its stage property."""
    definition = loop_definition(loop)
    schema = session.schemas[loop.type]
    stage_index = {stage.name: i for i, stage in enumerate(definition.stages)}
    on_path: dict[str, list[LoopEntity]] = {stage.name: [] for stage in definition.stages}
    exits: dict[str, list[LoopEntity]] = {stage.name: [] for stage in definition.exits}
    unplaced: list[LoopEntity] = []
    for rel_path in session.all_markdown:
        entity = session.lookup(rel_path)
        if entity.error is not None or not entity.is_entity or entity.type != loop.type:
            continue
        assert entity.frontmatter is not None
        value = entity.frontmatter.get(loop.property)
        kid = entity_kid(session, rel_path)
        title = _title(entity, schema)
        if not isinstance(value, str) or (value not in on_path and value not in exits):
            unplaced.append(LoopEntity(path=rel_path, kid=kid, title=title))
        elif value in exits:
            exits[value].append(LoopEntity(path=rel_path, kid=kid, title=title))
        else:
            index = stage_index[value]
            reached = definition.stages[: index + 1]
            following = definition.stages[index + 1] if index + 1 < len(stage_index) else None
            on_path[value].append(
                LoopEntity(
                    path=rel_path,
                    kid=kid,
                    title=title,
                    unmet=_first_of_each(
                        need
                        for stage in reached
                        for need in stage.needs
                        if not _met(session, schema, entity, need)
                    ),
                    next=following.name if following is not None else None,
                    missing_next=[
                        need
                        for need in (following.needs if following is not None else [])
                        if not _met(session, schema, entity, need)
                    ],
                )
            )
    return LoopReport(
        loop=definition,
        stages=[LoopPlacement(stage=name, entities=found) for name, found in on_path.items()],
        exits=[LoopPlacement(stage=name, entities=found) for name, found in exits.items()],
        unplaced=unplaced,
    )


def _first_of_each(needs: Iterable[LoopNeed]) -> list[LoopNeed]:
    """A need that a later stage repeats is reported once, at its first stage."""
    seen: dict[tuple[str | None, ...], LoopNeed] = {}
    for need in needs:
        seen.setdefault((need.kind, need.property, need.relation, need.type), need)
    return list(seen.values())


def _met(session: VaultSession, schema: Schema, entity: MarkdownFile, need: LoopNeed) -> bool:
    assert entity.frontmatter is not None
    if need.kind == "property":
        assert need.property is not None
        definition = schema.properties[need.property]
        return not is_empty(entity.frontmatter.get(need.property), definition.shape)
    return any(
        ref.relation == need.relation and ref.source_type == need.type
        for ref in session.references().to(entity.path)
    )


def _title(entity: MarkdownFile, schema: Schema) -> str:
    assert entity.frontmatter is not None
    declared = schema.properties.get(TITLE_KEY)
    value = entity.frontmatter.get(TITLE_KEY)
    if (
        declared is not None
        and declared.shape is ScalarType.STRING
        and isinstance(value, str)
        and value.strip()
    ):
        return value
    return PurePosixPath(entity.path).name


def need_label(need: LoopNeed) -> str:
    """Short form of a need: ``recorded_at``, or ``transcript in materials``."""
    if need.kind == "property":
        return str(need.property)
    return f"{need.type} in {need.inverse}"


def need_text(need: LoopNeed) -> str:
    """A need as the tail of "stage … needs …"."""
    if need.kind == "property":
        return f"`{need.property}`"
    return f"a `{need.type}` in `{need.inverse}` (`{need.relation}` pointing here)"


def unmet_issues(
    session: VaultSession, report: LoopReport, in_scope: Collection[str] | None = None
) -> list[Issue]:
    """One `loop-stage-unmet` issue per unmet need of each in-scope entity."""
    loop = report.loop
    issues: list[Issue] = []
    for placement in report.stages:
        for entity in placement.entities:
            if in_scope is not None and entity.path not in in_scope:
                continue
            line = session.lookup(entity.path).key_lines.get(loop.property)
            for need in entity.unmet:
                message = f"stage `{placement.stage}` of loop `{loop.name}` needs {need_text(need)}"
                if need.since != placement.stage:
                    message += f" (needed since `{need.since}`)"
                issues.append(
                    Issue(
                        code="loop-stage-unmet",
                        path=entity.path,
                        line=line,
                        field=loop.property,
                        message=message,
                    )
                )
    return issues
