---
name: knott
description: Create, update, and validate typed Markdown entities in a Knott vault (a directory containing .knott/). Use when working in a Knott vault, when asked to record knowledge as Markdown entities, when a file's frontmatter has a `type` key backed by a concept file in .knott/concepts/, or when `knott validate` reports issues to fix.
---

# Knott

A Knott vault is an ordinary directory of Markdown files with a `.knott/` directory at its root. **The Markdown files are the source of truth.** Knott adds concept files and validation on top; it never owns the data. Edit files directly, then validate.

## Concepts

- **Entity**: a Markdown file whose YAML frontmatter is a mapping with a `type` key. Files without frontmatter, or without `type`, are ordinary notes and are ignored.
- **Concept file**: `.knott/concepts/**/*.md`, one file per type. Its frontmatter is the type's schema: `name:` (the type's name; the file name and folder do not matter), `description`, and `properties`. Its body, if any, is a template for entity bodies.
- **Property**: a frontmatter value declared under `properties:`: a scalar (`string`, `integer`, `number`, `boolean`, `date`, `datetime`), an `enum`, a `reference`, a `file`, or a `list`, `object` or `map` of them, nested.
- **Reference**: a property with `type: reference` and a `target` type; its value points to another entity file by relative path (or by `kid`). It lives only on the source file; never add an inverse on the target.
- **Relation file**: `.knott/relations/**/*.md`, one file per relation, naming what a link means. Frontmatter: `name`, `description`, and optionally `inverse` (its name read from the target side), `symmetric: true` (goes both ways) or `acyclic: true` (must not loop). Its body says when to use it. A reference property opts in with `relation: <name>`.
- **File**: a property with `type: file`; its value names a file that is not an entity (audio, PDF, image, JSON), by a relative path in the vault or by a URI for a file kept elsewhere (`s3://bucket/key`, `gdrive:<id>`).
- **Connector file**: `.knott/connectors/**/*.md`, one file per URI scheme the vault allows. Frontmatter: `name` (the scheme) and `description`. Its body says how to open or move such files.
- **Loop file**: `.knott/loops/**/*.md`, one file per repeated process. It follows one `enum` property of a type (the entity's stage) and lists what each stage needs. See Loops below.
- **Kid**: a knott-managed identity, `kid: <lowercase uuid>`. Never invent or edit one; `knott validate --fix` adds it.

## Workflow

1. Run `knott types --verbose` to see each type's concept file, whether it has a template, its references and its properties (with nested shapes), and the vault's relations and connectors with their usage guidance. If it reports `schema-legacy-layout`, migrate first (see Commands).
2. Pick the relevant type and read its concept file: `description`, `properties`, which fields are `required: true`, and the body template.
3. Create or update the Markdown entity. Put it wherever it makes sense to a human; Knott does not dictate folders. For a new entity, start the body from the concept's template (`template: yes`): keep its headings, fill each section, and delete a section's `<!-- … -->` guidance once it is filled. Knott never checks the body.
4. Write references as relative paths (see below).
5. Run `knott validate --fix <file>` after creating an entity (it adds the `kid`), and `knott validate <file>` after **every** change.
6. Fix every reported issue and validate again before finishing.

A concept file looks like this (`*` in `knott types --verbose` marks `required: true`):

```markdown
---
name: transcript
description: Transcript of recorded spoken content.
properties:
  title:        { type: string, required: true }
  derived_from: { type: reference, target: script }
---
# Transcript

<!-- One paragraph: who speaks and what it covers. -->
```

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
- An empty or `null` value counts as missing (for a `list`, `[]` does too).
- Top-level keys not declared in `properties` are allowed and are not checked.

## Structured properties

`knott types --verbose` shows shapes such as `list of object` and `map of map of string`, with object fields indented below and `*` marking required ones. Write them as ordinary YAML:

```yaml
type: lexeme
lemma: draugas
tags: [noun, a1]                # list of string
senses:                         # list of object (fields: id*, ru*)
  - {id: friend, ru: друг}
forms:                          # map of map of string: free keys
  sg: {nom: draũgas, gen: draũgo}
```

- An `enum` accepts **only** its listed options. `knott types --verbose` prints them under the property (`one of: m | f`, or one line per option with its meaning). Copy an option exactly: it is case-sensitive, and a synonym (`female` for `f`) is `attribute-unknown-option`. Quote an option that YAML would read as a boolean, number or date (`"no"`, `"1"`). Never add an option to a concept just to make a value pass.
- An `object` accepts **only** its declared fields; any other key is an error (`attribute-unknown-field`). A `map` accepts any string keys.
- A required list needs at least one item. Never leave a list item or map value empty (`[a, null]`, `{nom: ~}`).
- Strict typing applies at every level: quote `"no"`, `"42"`, and so on inside lists and objects too.
- Issues name the exact location, e.g. `senses[1].ru` or `forms.sg.acc`.

## Writing references

Each reference is resolved relative to the directory of the file that contains it and must point to an existing `.md` entity, inside the vault, whose `type` is one of the property's targets (`target: [episode, meeting]` accepts either).

Preferred form, a quoted Markdown link (clickable in Obsidian):

```yaml
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
sources:
  - "[Episode 42](../scripts/episode-42.md)"
  - "[Notes](<../notes/my notes.md>)"   # use <…> or %20 for spaces
speakers:
  - person: "[Ana](../people/ana.md)"
    role: host
```

A plain relative path also works: `derived_from: ../scripts/episode-42.md`.

Rules:

- **Cardinality is strict.** `reference` holds exactly one reference; `list of reference` holds a list, even for one item. Writing the other form is `relation-invalid-value`. A required list needs at least one reference.
- References can sit inside a `list`, `object` or `map` (`speakers[].person` in `knott types --verbose`). Issues name the exact location, e.g. `speakers[1].person`.
- **Always quote** a Markdown link. Unquoted `[label](path)` is invalid YAML.
- No wikilinks (`[[note]]`), URLs, `#fragments`, or absolute paths.
- Paths are case-sensitive, even on macOS.
- `kid:<uuid>` also works (`- kid:3f2b8c1e-…`), and survives the target being moved. Use it when you were given a `kid`; otherwise prefer the Markdown link. Never wrap it in a link.

## Relations

`knott types --verbose` shows the relation a property names after its type (`affects  list of reference → concept  (about)`) and lists every relation at the end, with its guidance:

```
relations:
  supersedes  inverse: superseded_by  acyclic
    This entity replaces the target entirely. The target is kept unchanged as history.
    Use `supersedes` when the old record is no longer the current answer: …
```

- **Pick the property by its relation's guidance.** When two fit (`supersedes` vs `amends`), the guidance says which one.
- **Never write the inverse.** `superseded_by` is not a property; it is how `knott refs` labels incoming `supersedes` links. Store a `symmetric` link on one side only.
- **Find who links to an entity** with `knott refs <file>` before renaming, deleting or replacing it:

  ```
  $ knott refs specs/0005-concept-files.md
  specs/0005-concept-files.md  spec

  amended_by
    specs/0006-relation-definitions.md  spec  amends[0]
  ```

  Symmetric groups end each line with `←` (the other side stores it), `→` (this file does) or `⇄` (both).
- `relation-cycle`: an `acyclic` relation loops (`decisions/a.md → decisions/b.md → decisions/a.md`). Remove the reference that is wrong (for `supersedes` and `amends`, the newer entity is the source).
- Writing a concept file: put `relation:` on a `reference` shape (for a list, on its `items`), on one line straight after `type` (`items: { type: reference, relation: about, target: concept }`), and name only relations defined in `.knott/relations/` (`relation-unknown` otherwise). A reference without `relation:` is a plain, inline link.

## Files

`knott types --verbose` shows a file property as `audio*  file .mp3 | .wav` (the extensions it accepts) and lists the vault's connectors at the end.

```yaml
audio: ../audio/episode-42.mp3
images:
  - "[the whiteboard](../img/board.jpg)"
  - s3://talks/episode-42.png
  - gdrive:1AbCdEf
```

- **A file in the vault** is a relative path, plain or a quoted Markdown link, case-sensitive. It must exist before you validate (`file-not-found`) and have an accepted extension (`file-extension-mismatch`).
- **A file kept elsewhere** is a URI whose scheme is a listed connector. Read the connector's guidance for what follows the scheme. Never invent a scheme: an unlisted one is `file-unknown-connector`, and a web address (`https://…`) is one too unless `https` is a connector.
- Write a URI on its own, never in a Markdown link. Quote it when it contains `#` or `: `.
- `file` holds exactly one value; `list of file` holds a list, even for one. Each item is checked on its own.
- A file whose name has a colon is written `./a:b.json`.
- Knott does not move files. Put the file in place (or upload it with the tool the connector's guidance names), then write the value.

## Kids

- **When copying a file to start a new entity, delete its `kid:` line**, then run `knott validate --fix <new file>`. Otherwise both files claim the same `kid` (`kid-duplicate`).
- Never change an existing `kid`; other files and tools may refer to it.
- `kid-invalid`: write the canonical form the message gives.

## Loops

A vault can define **loops** in `.knott/loops/`: a process that entities of one type go through, such as producing an episode. A loop follows one `enum` property (often `status`); its value is the entity's stage. Each stage lists what it needs: properties that are set, and entities that point at this one (`transcript in materials`).

- `knott types --verbose` ends with a `loops:` section: each loop's stages, needs, and guidance on what to do at each stage. Read it before working on an entity of that type.
- `knott loops <name>` lists every entity under its stage, with `next: <stage> — missing …` or `next: <stage> — ready`.
- **Move an entity forward in this order:** add what the next stage needs, then change the stage property. Set the next stage only when `knott loops` says `ready`.
- A stage set too early is `loop-stage-unmet` in `knott validate`. Fix it by adding what is missing, or by setting the property back. Never remove a need from a loop file just to make an entity pass.
- A value the loop does not list as a stage (such as `dropped`) is a side exit: it needs nothing.

## Obsidian settings

For vaults edited in Obsidian, set Files & links → *New link format* to **Relative path to file** and turn **off** *Use [[Wikilinks]]*. Otherwise Obsidian may rewrite links on rename into forms `knott validate` rejects.

## Commands

```sh
knott types [--verbose]          # list types (exit 1 if a concept file has errors)
knott validate [PATH...]         # check concept files + all entities, or only PATHs
knott validate --format json     # {ok, stats, issues[]} for machine reading
knott validate --fix [PATH...]   # add a kid to entities that have none, then validate
knott refs PATH [--format json]  # who references an entity (PATH or kid:<uuid>), by relation
knott loops [NAME] [--format json]  # entities by stage of a loop, and what each still needs
knott init [PATH]                # create .knott/ (never overwrites)
knott view [PATH] [--no-open] [-o FILE]  # write an HTML diagram of types and references
knott migrate [PATH]             # convert a pre-0.5 .knott/schemas/ into .knott/concepts/
```

If any command reports `schema-legacy-layout`, the vault still uses `.knott/schemas/`. Run `knott migrate`, then review the diff (`git diff`): check the new concept files, especially fields converted to `list of reference`.

Exit codes: `0` valid, `1` validation issues, `2` usage error (no vault, bad path, malformed `.knott/config.yaml`).

Each issue has a stable `code`, the file `path`, a `line` when known, the `field`, and a `message` that says what was expected. Fix the cause the message names; do not delete required fields or references just to silence an error.

If `uvx` is how Knott is run here, prefix commands with `uvx`: `uvx knott validate path/to/file.md`.
