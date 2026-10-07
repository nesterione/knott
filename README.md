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

Define a type in `my-vault/.knott/schemas/script.yaml`:

```yaml
type: script
description: A script for a recorded episode.
attributes:
  title:
    type: string
    required: true
```

and one that relates to it, `.knott/schemas/transcript.yaml`:

```yaml
type: transcript
relations:
  derived_from:
    target: script
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
| `knott init [PATH]` | Create `.knott/schemas/` and `.knott/config.yaml` |
| `knott validate [PATH...]` | Check all schemas, plus all entities or those under `PATH` (`--format json` for agents) |
| `knott types [--verbose]` | List discovered types |
| `knott version` | Print the installed version |
| `knott skill install [PATH]` | Install the bundled Agent Skill to `.claude/skills` and/or `.agents/skills` (`--claude`, `--agents`; asks interactively without flags) |

Exit codes: `0` valid, `1` validation issues, `2` usage or configuration error.

## Schemas

Schemas live in `.knott/schemas/**/*.yaml`, one type per file. Attribute types: `string`, `integer`, `number`, `boolean`, `date`, `datetime`. Typing is strict: an unquoted `no` is a boolean, not a string. Relations name a `target` type and are stored only on the source entity.

## Relations

A relation value is a relative path or a quoted Markdown link, or a list of them, resolved relative to the containing file:

```yaml
derived_from: ../scripts/episode-42.md
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
```

Wikilinks, URLs, `#fragments`, and absolute paths are rejected. Matching is case-sensitive on every OS.

### Obsidian

Markdown links in properties are clickable in Obsidian 1.11+ and are updated on rename. Use these settings:

- Files & links → *New link format*: **Relative path to file**
- *Use [[Wikilinks]]*: **off**

## Python API

```python
from knott import Knott

vault = Knott.open(".")              # walks up to the vault root
result = vault.validate()            # or vault.validate(["transcripts/foo.md"])
result.ok, result.issues, result.stats
vault.types()                        # ["script", "transcript"]
```

Validation problems come back as data; only usage errors raise (`KnottError` subclasses).

## For agents

Knott ships an Agent Skill describing how to read schemas, write entities and relations, and validate ([`SKILL.md`](src/knott/_skills/knott/SKILL.md)). Install it into a project:

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
