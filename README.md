# knott

A local, file-first knowledge layer for AI agents.

Markdown files are the source of truth. Knott adds structure (typed entities), semantics (relations between them), and validation, without turning your notes into an opaque database. A Knott vault stays useful without Knott: browse it in a file manager, read it in any editor, open it in Obsidian, diff it in Git.

## Install

```sh
uvx knott --help        # run without installing
uv add knott            # or add it to a project
```

Requires Python 3.12+.

## Quick start

```sh
mkdir my-vault && knott init my-vault
```

Each type is a Markdown concept file in `.knott/concepts/`. Its frontmatter is the schema. `my-vault/.knott/concepts/script.md`:

```markdown
---
name: script
description: A script for a recorded episode.
properties:
  title:
    type: string
    required: true
---
```

and one that refers to it, `.knott/concepts/transcript.md`. Its body is a template that agents copy when they write a transcript:

```markdown
---
name: transcript
properties:
  title:
    type: string
  derived_from:
    type: reference
    target: script
---
# Transcript

<!-- Who speaks, and what the recording covers. -->
```

Write entities as ordinary Markdown with frontmatter, anywhere in the vault:

```markdown
---
type: transcript
title: Episode 42 transcript
derived_from: "[Episode 42](../scripts/foo.md)"
---
# Transcript
```

Then validate:

```sh
$ knott validate
✓ 2 schemas
✓ 2 entities
✓ 1 relation
✓ vault is valid
```

## Commands

| Command | Purpose |
|---|---|
| `knott init [PATH]` | Create `.knott/concepts/` and `.knott/config.yaml` |
| `knott validate [PATH...]` | Check all schemas, plus all entities or those under `PATH` (`--format json` for agents, `--fix` to add missing `kid`s) |
| `knott types [--verbose]` | List discovered types (`--verbose`: properties, nested shapes, references and whether a template exists) |
| `knott migrate [PATH]` | Convert a pre-0.5 `.knott/schemas/` folder into concept files, then validate |
| `knott view [PATH]` | Draw the ontology as an HTML page and open it (`-o FILE`, `--no-open`) |
| `knott version` | Print the installed version |
| `knott skill install [PATH]` | Install the bundled Agent Skill to `.claude/skills` and/or `.agents/skills` (`--claude`, `--agents`; asks interactively without flags) |

Exit codes: `0` valid, `1` validation issues, `2` usage or configuration error.

## Concept files

Concept files live in `.knott/concepts/**/*.md`, one type per file, identified by `name:`. All fields go in one `properties` map. Value types: `string`, `integer`, `number`, `boolean`, `date`, `datetime`, plus `list`, `object` and `map` built from them and nested to any depth. Typing is strict: an unquoted `no` is a boolean, not a string.

A property with `type: reference` points at another entity. It can sit anywhere a shape can, and `target` may name several types. Problems name their exact location, e.g. `speakers[1].person`:

```yaml
properties:
  recording_of: { type: reference, target: [episode, meeting] }
  speakers:
    type: list
    items:
      type: object
      fields:
        person: { type: reference, target: person, required: true }
        role:   { type: string }
```

The body of a concept file is an optional template for entity bodies: real headings, with a `<!-- -->` comment under each saying what goes there. Knott stores it and never checks entities against it.

## References

A reference is a relative path or a quoted Markdown link, resolved relative to the containing file. References are stored only on the source entity. `type: reference` holds exactly one; for several, declare a `list` of references:

```yaml
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
sources:
  - ../scripts/episode-42.md
  - "[Notes](../notes/episode-42.md)"
```

Wikilinks, URLs, `#fragments`, and absolute paths are rejected. Matching is case-sensitive on every OS.

### Stable identity

`knott validate --fix` gives every entity a `kid`, a knott-managed UUID that survives moves and renames. A reference can then name it as `kid:<uuid>`. A concept file can require one with `kid: required`. Markdown links stay the recommended form; use `kid:` where a reference must survive renames.

```yaml
kid: 3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21
includes:
  - kid:0192f4a1-7c3e-4b2a-9f10-3d5e8c2b4a61
```

### Obsidian

Markdown links in properties are clickable in Obsidian 1.11+ and are updated on rename. Use these settings:

- Files & links → *New link format*: **Relative path to file**
- *Use [[Wikilinks]]*: **off**

## Upgrading from 0.4

Knott 0.5 reads types from `.knott/concepts/` only. A vault that still has `.knott/schemas/` reports one issue, `schema-legacy-layout`, and nothing else is checked until you convert it:

```sh
$ knott migrate
+ .knott/concepts/compilation.md
+ .knott/concepts/media/episode.md
+ .knott/concepts/script.md
  list of reference: compilation.sources
- .knott/schemas/

✓ 3 schemas
✓ 4 entities
✓ 4 relations
✓ vault is valid
```

- Each YAML schema becomes a concept file at the same relative path. `type` becomes `name`, and `attributes` and `relations` merge into `properties`.
- A relation becomes a `reference`, or a `list` of references when any entity already stores a list there (the `list of reference:` lines).
- Entities are not changed. From now on, a single reference accepts exactly one value and a list reference needs a list.
- It writes nothing if any schema can't be converted or a concept file already exists (exit `2`). Review the diff in Git afterwards.

The Python API changed too: `OntologyType.attributes` and `.relations` are now one `properties` list, and `OntologyRelation` is gone. See [decision 0010](docs/decisions/0010-concept-files-and-reference-properties.md) and [`knott migrate`](docs/commands/migrate.md).

## Python API

```python
from knott import Knott

vault = Knott.open(".")              # walks up to the vault root
result = vault.validate()            # or vault.validate(["transcripts/foo.md"])
result.ok, result.issues, result.stats
vault.types()                        # ["script", "transcript"]
vault.ontology()                     # Ontology(vault, types, schema_issues)
for t in vault.ontology().types:
    t.properties, t.template, t.references()   # references(): [("speakers[].person", …), …]
```

Validation problems come back as data; only usage errors raise (`KnottError` subclasses).

## For agents

Knott ships an Agent Skill describing how to read concept files, write entities and references, and validate ([`SKILL.md`](src/knott/_skills/knott/SKILL.md)). Install it into a project:

```sh
knott skill install            # pick targets interactively
knott skill install --claude   # .claude/skills/knott/ (Claude Code)
knott skill install --agents   # .agents/skills/knott/ (Codex and other agents)
```

## Development

```sh
uv sync
uv run pytest
uv run ruff check src tests
uv run mypy
```
