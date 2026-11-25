---
type: spec
title: "0010: Loops"
status: accepted
created_on: 2026-11-25
realizes:
  - "[Loops](../intents/loops.md)"
decisions:
  - "[0001](../decisions/0001-markdown-is-source-of-truth.md)"
  - "[0003](../decisions/0003-source-side-relations.md)"
  - "[0005](../decisions/0005-empty-values.md)"
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Attribute](../concepts/attribute.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Ontology](../concepts/ontology.md)"
---
# 0010: Loops

## Summary

A vault can define **loops**: a repeated process that entities of one type pass through, such as producing a podcast episode. A loop file names a type and one of its enum properties, and lists what each stage needs: properties that are set, and entities that point at this one. `knott validate` reports an entity that claims a stage whose needs are not met. A new command, `knott loops`, and a board in `knott view` show every entity under its stage with what is missing for the next one. Knott describes and checks a loop; it never changes a stage and never creates a file. The change is additive.

## Behaviour

### Loop files

Each loop is one Markdown file, discovered from `.knott/loops/**/*.md`. Subfolders are only for organisation; other file types are ignored.

```markdown
---
name: episode-production
description: From an episode idea to a published episode.
type: episode
property: status
stages:
  idea:
  planned:   { needs: [participants] }
  recorded:  { needs: [recorded_at, materials: transcript] }
  published: { needs: [published_at, links, materials: [summary, topics]] }
---
Tasks and the topic backlog live in GitHub Issues, not here.

## recorded

Export the transcript into the episode folder, then run the review.
```

The frontmatter is the definition. Keys are closed:

| Key | Required | Value |
|---|---|---|
| `name` | yes | `^[a-z][a-z0-9_-]*$`. Loop names are a namespace of their own. |
| `description` | no | string |
| `type` | yes | the name of one concept |
| `property` | yes | a top-level property of that concept whose shape is `enum` |
| `stages` | yes | a non-empty mapping: stage → empty, or a mapping whose only key is `needs` |

- A vault may define any number of loops. Two loops may follow different properties of one type. Two loops that name the same `type` and `property` are `schema-duplicate-loop`.
- **Stages.** Each key of `stages` must be an option of the enum. The order they are written in is the **path**. An option of the enum that `stages` leaves out is a **side exit** (`dropped`, `superseded`): it has no needs and no next stage.
- **Needs.** `needs` is a list. Each item is one of:
  - a string: the name of a top-level property of the type. It is met when the property is not absent, by the rules of [0005](../decisions/0005-empty-values.md). The value is not looked at otherwise.
  - a mapping with one key, `<inverse>: <type>` or `<inverse>: [<type>, …]`. `<inverse>` is the `inverse` of a relation. It is met when, for **each** listed type, at least one entity of that type has a reference that names the relation and resolves to this entity (reverse lookup, §10 of SPEC.md).
- **Needs add up.** An entity at a stage must meet the needs of that stage and of every stage before it on the path. A need is written once, at the stage where it first applies.
- A need checks that something exists. It never checks a value, a date, a count above one, or a file's content.
- **Guidance.** The body is optional guidance, stored verbatim. A line `## <name>`, where `<name>` is an option of the enum, starts the guidance for that stage or side exit; it runs to the next such line. The text before the first such line is the loop's general guidance. Each part is kept as written, without the blank lines around it; a blank part is no guidance. A `##` line with any other text is part of the section it is in. The body is never checked against anything.

### Checks on loop files

Run on every command, after all concept and relation files are read.

- A file with no frontmatter, or invalid YAML, is `schema-invalid-yaml`.
- A missing or invalid `name` is `schema-invalid-field` and defines no loop. A missing `type`, `property` or `stages` is `schema-invalid-field`, reported at line 1, and the loop is not loaded. An unknown key is `schema-invalid-field` with a "did you mean" suggestion. An invalid `description` is `schema-invalid-field` and the loop still loads without it.
- Two files with one `name`, or with the same `type` and `property`, are `schema-duplicate-loop`, reported at the second file in path order and naming both. The second defines no loop.
- A malformed `stages` or `needs` (not a mapping, empty, a key that is not a string, a key other than `needs`, a need that is neither a string nor a one-key mapping) is `schema-invalid-field` at that line. A stage key that YAML reads as a boolean, number or date gets the hint to quote it.
- Each of these is `loop-invalid-target`, at the line of the value:
  - `type` names no concept;
  - `property` is not a top-level property of the type, or its shape is not `enum` (a list of enums included);
  - a stage is not an option of the enum; the message lists the options, with a "did you mean" suggestion;
  - a property need names no top-level property of the type, or names the loop's own `property`;
  - an inverse need names no relation's `inverse`;
  - a type in an inverse need names no concept, or that concept has no reference property that names the relation and can target the loop's type.
- A loop with a `loop-invalid-target`, or a malformed `stages` or `needs`, is not loaded: entities are not checked against it, and `knott loops` and `knott view` leave it out.

### Entities

For each loaded loop, each entity of its type is placed by the value of the loop's property:

| Value | Placement |
|---|---|
| a stage on the path | that stage |
| a side exit | that side exit |
| absent, or not an option, or not a string | no stage |

- An entity with invalid frontmatter is not placed.
- **Unmet needs.** For an entity placed at a stage on the path, each need of that stage and of every earlier stage that is not met is one `loop-stage-unmet` issue.
- **Missing for next.** For an entity at a stage that is not the last on the path, the needs of the next stage that are not met are its *missing for next*. They are not issues. They are shown by `knott loops` and `knott view` only.
- An entity at a side exit, or with no stage, has no unmet needs and no missing for next.
- A reference counts toward an inverse need when it resolves to the entity, as in reverse lookup: a reference that fails the target-type check still counts, and `validate` reports the mismatch on its own.

### Messages

```
✗ episodes/ep-001/episode.md:5  status
  stage `published` of loop `episode-production` needs `published_at`
✗ episodes/ep-001/episode.md:5  status
  stage `published` of loop `episode-production` needs a `summary` in `materials` (`material_for` pointing here)
✗ episodes/ep-001/episode.md:5  status
  stage `published` of loop `episode-production` needs `recorded_at` (needed since `recorded`)
```

The stage named first is the entity's stage. `(needed since …)` is added when the need belongs to an earlier stage.

## Issue codes

| Code | Stage | When | `field` / `line` |
|---|---|---|---|
| `schema-duplicate-loop` | schema | two loop files have one `name`, or the same `type` and `property` | `name`, or `property` / that line in the second file |
| `loop-invalid-target` | schema | a loop names a type, property, stage, need or inverse that does not exist or does not fit | the key (`type`, `property`, `stages`, `needs`) / the value's line |
| `loop-stage-unmet` | entity | an entity is at a stage and a need of that stage, or of an earlier one, is not met | the loop's property / the property's line in the entity |

`schema-invalid-yaml` and `schema-invalid-field` also cover loop files. No existing code changes meaning.

## CLI and API

### `knott validate`

Reports the schema codes above on every run, and `loop-stage-unmet` for each entity in the run's scope. The check reads the whole vault to find incoming references, as `relation-cycle` does. An entity outside the scope is not reported, even when a file in the scope is what it lacks. No change to the stats.

### `knott loops [NAME] [--format text|json]`

Read-only. The vault is found from the current directory. Work in progress is not an error: unmet needs and missing items never change the exit code.

Without `NAME`, one line per loop, sorted by name: the name, `<type>.<property>`, then each stage on the path with its entity count, then the side exits in parentheses, in the enum's order, then `no stage N` when N is not 0:

```
$ knott loops
episode-production  episode.status  idea 0 · planned 1 · recorded 1 · published 0 · (dropped 0)
idea-review         idea.status     open 3 · trying 1 · adopted 2 · (dropped 1)
```

With `NAME`, each stage on the path that has entities, then each side exit that has entities, then `no stage`. Entities are sorted by path. Under each entity, indented, one line per unmet need (`✗ needs …`), then one line `next: <stage> — missing <items>`, or `next: <stage> — ready` when nothing is missing. The last stage has no `next:` line.

```
$ knott loops episode-production
planned
  episodes/ep-002-agents/episode.md
    next: recorded — missing recorded_at, transcript in materials
recorded
  episodes/ep-001-robots-coding-agents/episode.md
    next: published — missing published_at, links, summary in materials
```

- A vault with no loops prints nothing and exits `0`. A `NAME` that no loaded loop has is `error: no loop named <NAME>` on stderr and exit `2`.
- If schema errors exist, it still prints the loops it could load, writes the errors to stderr, and exits `1`, as `knott types` does.
- `--format json` prints `{"loops": [...]}`, each loop as in the Python API below, whether or not `NAME` is given (`NAME` keeps one loop).

### `knott types --verbose`

After the connectors, a `loops:` section lists every loop, sorted by name: the name and `<type>.<property>` indented by two spaces; then the description; then the path as `stages: a → b → c` and, when there are any, `exits: x | y`; then each stage that has needs as `<stage> needs: <items>`; then the guidance. Each of these lines is indented by four spaces. A vault without loops has no `loops:` section.

### `knott view`

- A type's panel gains a **Loops** section: for each loop of the type, its name, the stages with entity counts, and each stage's needs.
- A **Loops (N)** button in the header, hidden when the vault has no loaded loop, opens a board. One loop is shown at a time; a dropdown switches, and the URL hash `#loop=<name>` opens one directly.
- Columns are the stages on the path, in order, then the side exits, dimmed, then `no stage` when it has entities. Each column header shows the entity count; clicking it shows the stage's needs and guidance (HTML-escaped).
- Each entity is a card: its `title` when the type has a top-level string property of that name and the entity sets it, otherwise the file name; its vault-relative path, as text; and its missing for next. A card with unmet needs is marked and lists them.
- The embedded data gains `loops`, the same data as `knott loops --format json`. The page now holds the titles and paths of entities whose type has a loop; nothing else about entities is embedded.
- The page stays static: no server, no network, no editing. Cards are not links.

### Python API

```python
ontology.loops        # [LoopDefinition(name, description, type, property, stages, exits, guidance, path), …]
vault.loops()         # list[LoopReport], sorted by name
vault.loops("episode-production")   # one LoopReport; raises KnottError when no loop has that name
```

- `LoopDefinition.stages` is `list[LoopStage(name, needs, guidance)]` in path order; `exits` is `list[LoopStage]` in the enum's order, with empty `needs`.
- `LoopNeed(kind, property, inverse, relation, type, since)`: `kind` is `property` or `inverse`; an inverse need that lists several types is one `LoopNeed` per type. `since` is the stage that declares it.
- `LoopReport(loop: LoopDefinition, stages: list[LoopPlacement], exits: list[LoopPlacement], unplaced: list[LoopEntity])`.
- `LoopPlacement(stage: str, entities: list[LoopEntity])`.
- `LoopEntity(path, kid, title, unmet: list[LoopNeed], next: str | None, missing_next: list[LoopNeed])`.
- These types are exported from `knott`.

### Agent skill

The bundled skill says: before changing a property that a loop follows, read the loop in `knott types --verbose`; run `knott loops <name>` to see what an entity still needs; set the next stage only when it says `ready`.

## Edge cases

| Case | Result |
|---|---|
| `status: published`, `published_at` empty | `loop-stage-unmet` |
| `status: published`, `recorded_at` empty (a need of `recorded`) | `loop-stage-unmet`, "needed since `recorded`" |
| `status: recorded`, nothing for `published` yet | valid; shown as missing for next |
| `status: dropped` (a side exit), nothing else set | valid; no loop issues |
| `status:` absent | no stage; `attribute-missing` only if the property is required |
| `status: publshed` | `attribute-unknown-option`; no stage; no loop issues |
| `materials: [summary, topics]`, a summary exists but no topics | one `loop-stage-unmet`, for `topics` |
| Two transcripts point at one episode | the need is met; a need never counts above one |
| A transcript points at the episode through a property that names no relation | does not count: the need names a relation's inverse |
| A reference that resolves to the entity but fails the target-type check | counts; `relation-target-type-mismatch` is reported on the source |
| `knott validate transcripts/x.md` after the only transcript was deleted | the episode is out of scope and is not reported; a full run reports it |
| A stage in `stages` that is not an option | `loop-invalid-target`; the loop is not loaded |
| An entity already at a late stage when the loop is added, without an early need (a published pilot that never had a transcript) | `loop-stage-unmet`; needs add up and have no exceptions. Add the artifact, or leave that need out of the loop |
| `stages` lists the options in another order than the enum | valid; the loop's order is the path |
| `stages` lists one stage | valid; no entity has a next stage |
| The enum gains an option the loop does not list | valid; it is a side exit |
| The enum loses an option the loop lists | `loop-invalid-target` at that stage |
| A loop on a type with no entities | valid; every count is 0 |
| A `## recorded` line inside a fenced code block in the body | starts the guidance for `recorded`; the body is split by lines only |
| A property need that is a `reference` or `file` property | met when the value is not absent; whether it resolves is checked by the existing codes |

## Out of scope

- A stage that is derived from links and not stored, and a process that crosses types. See the [intent](../intents/loops.md).
- Needs on values: a date in the past, a count, a nested path, a property of a linked entity.
- Needs written as alternatives ("a transcript or a script").
- Transition rules: which stage may follow which, and who may change it. An entity may be set to any stage whose needs it meets.
- History: when an entity entered a stage, and how long it stayed.
- Anything that acts: changing a stage, creating a file from a template, a fix command.
- Editing from `knott view`, and links from a card to its file.
- A loop that follows a list of enums, or a nested property.

## Compatibility

Additive. A vault without `.knott/loops/` behaves exactly as in 0.8.0. Adding a loop can make existing entities invalid; `knott validate` lists them. Ontology API additions only. Version 0.9.0.

SPEC.md uses "loop" for a cycle of references in a few places (§9 Cycles, §13). Implementing this spec rewords them to "cycle", so that "loop" has one meaning.
