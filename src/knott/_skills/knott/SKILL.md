---
name: knott
description: Create, update, and validate typed Markdown entities in a Knott vault (a directory containing .knott/). Use when working in a Knott vault, when asked to record knowledge as Markdown entities, when a file's frontmatter has a `type` key backed by .knott/schemas/, or when `knott validate` reports issues to fix.
---

# Knott

A Knott vault is an ordinary directory of Markdown files with a `.knott/` directory at its root. **The Markdown files are the source of truth.** Knott adds schemas and validation on top; it never owns the data. Edit files directly, then validate.

## Concepts

- **Entity**: a Markdown file whose YAML frontmatter is a mapping with a `type` key. Files without frontmatter, or without `type`, are ordinary notes and are ignored.
- **Schema**: `.knott/schemas/**/*.yaml`, one file per type. The `type:` value inside the file is the type's name; the file name and folder do not matter.
- **Attribute**: a scalar frontmatter value declared under `attributes:` (`string`, `integer`, `number`, `boolean`, `date`, `datetime`).
- **Relation**: a frontmatter value declared under `relations:` that points to another entity file by relative path. The relation lives only on the source file; never add an inverse on the target.

## Workflow

1. Run `knott types` (or `knott types --verbose` to see each schema file) and look in `.knott/schemas/`.
2. Pick the relevant type and read its schema YAML: `description`, `attributes`, `relations`, and which fields are `required: true`.
3. Create or update the Markdown entity. Put it wherever it makes sense to a human; Knott does not dictate folders.
4. Write relations as relative paths (see below).
5. Run `knott validate <file>` after **every** change.
6. Fix every reported issue and validate again before finishing.

## Writing an entity

```markdown
---
type: transcript
title: Episode 42 transcript
created_at: 2026-10-06
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
---
# Episode 42

Body: any Markdown. Knott does not read it.
```

Typing is strict, with no coercion:

- `string`: quote values YAML would read as something else: `"42"`, `"no"`, `"yes"`, `"on"`, `"off"`, `"2026-10-06"`.
- `integer`: `3`, not `3.0` or `true`. `number`: `3` or `3.5`. `boolean`: `true` / `false` only (not `yes`/`no`/`on`/`off`).
- `date`: `2026-10-06`. `datetime`: `2026-10-06T10:30:00` (a time is required).
- An empty or `null` value counts as missing (for relations, `[]` does too).
- Keys not declared in the schema are allowed and are not checked.

## Writing relations

A relation value is one reference or a list of references. Each reference is resolved relative to the directory of the file that contains it and must point to an existing `.md` entity, inside the vault, whose `type` equals the relation's `target`.

Preferred form, a quoted Markdown link (clickable in Obsidian):

```yaml
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
sources:
  - "[Episode 42](../scripts/episode-42.md)"
  - "[Notes](<../notes/my notes.md>)"   # use <…> or %20 for spaces
```

A plain relative path also works: `derived_from: ../scripts/episode-42.md`.

Rules:

- **Always quote** a Markdown link. Unquoted `[label](path)` is invalid YAML.
- No wikilinks (`[[note]]`), URLs, `#fragments`, or absolute paths.
- Paths are case-sensitive, even on macOS.

## Obsidian settings

For vaults edited in Obsidian, set Files & links → *New link format* to **Relative path to file** and turn **off** *Use [[Wikilinks]]*. Otherwise Obsidian may rewrite links on rename into forms `knott validate` rejects.

## Commands

```sh
knott types [--verbose]          # list types (exit 1 if a schema has errors)
knott validate [PATH...]         # check schemas + all entities, or only PATHs
knott validate --format json     # {ok, stats, issues[]} for machine reading
knott init [PATH]                # create .knott/ (never overwrites)
knott view [PATH] [--no-open] [-o FILE]  # write an HTML diagram of types and relations
```

Exit codes: `0` valid, `1` validation issues, `2` usage error (no vault, bad path, malformed `.knott/config.yaml`).

Each issue has a stable `code`, the file `path`, a `line` when known, the `field`, and a `message` that says what was expected. Fix the cause the message names; do not delete required fields or relations just to silence an error.

If `uvx` is how Knott is run here, prefix commands with `uvx`: `uvx knott validate path/to/file.md`.
