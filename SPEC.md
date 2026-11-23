# Knott v0 — Technical Specification

## 1. Goal

Knott is a local, file-first knowledge layer for AI agents.

The core principle:

> Markdown files are the source of truth.
> Knott adds structure, semantics, and validation without turning the knowledge base into an opaque database.

A Knott vault must remain useful without Knott itself:

- A human can browse it with a normal file manager.
- Markdown files are directly readable.
- Relations stay clickable in tools such as Obsidian (see §11).
- Git produces meaningful text diffs.
- The CLI is a tooling layer over the files, not the owner of the data.

The goal of v0 is to validate the core model:

```
typed Markdown entities + schemas + semantic relations
```

It is explicitly **not** the goal of v0 to build a full knowledge graph, semantic search engine, or ontology platform.

---

## 2. Technology

Python 3.12+, with a modern toolchain:

- `uv`, `pyproject.toml`, `src/` layout
- `pytest`
- `ruff`
- `mypy --strict`

The package name on PyPI is `knott` (free as of 2026-10-06). It must run as:

```sh
uvx knott ...
```

and as a regular dependency:

```sh
uv add knott
knott ...
```

CLI entry point:

```toml
[project.scripts]
knott = "knott.cli:app"
```

Libraries:

- Typer for the CLI
- Pydantic v2 for internal models
- PyYAML (`safe_load` / `compose` only) for YAML parsing

Prefer minimal dependencies.

### Architectural constraint

The CLI must not contain the core implementation. Keep a stable API boundary:

```
CLI  ──┐
       ├──▶  Knott API (api.py)  ──▶  core  ──▶  filesystem
Python ┘
```

A reasonable initial layout:

```
src/knott/
  __init__.py      # exports Knott and public result types
  cli.py           # thin Typer adapter
  api.py           # Knott class: open / validate / types
  models.py        # public result types (Issue, ValidationResult, ...)
  errors.py
  schema/
    loader.py      # concept files
    migrate.py     # .knott/schemas/ → .knott/concepts/
    models.py
    validator.py
  vault/
    discovery.py
    entity.py
    links.py       # relation value parsing + path resolution
```

Exact module names are not important; the separation is.

The implementation is Python-first, but a future move of hot paths to Rust should stay possible. The only rule that follows from this in v0: **public API inputs and outputs are plain data** (`str`, `Path`, numbers, lists, and frozen dataclasses/Pydantic models made of those). Never expose PyYAML nodes or other internal parser objects. Do not build backend or plugin abstractions for this.

---

## 3. Vault

A vault is an ordinary directory that contains `.knott/`.

```
my-vault/
├── .knott/
│   ├── config.yaml
│   └── concepts/
│       ├── script.md
│       ├── transcript.md
│       └── feedback.md
├── scripts/
│   └── episode-42.md
├── transcripts/
│   └── episode-42.md
└── feedback/
    └── episode-42-review.md
```

Knott does not dictate where entity files live. Users organize Markdown however is useful to humans.

### Vault root

The vault root is the nearest directory, starting at the current working directory (or the path given to the CLI or API) and walking up, that contains a `.knott/` directory. If none is found, the CLI exits with code `2`.

### Vault config

`.knott/config.yaml` records the Knott version the vault was initialized with:

```yaml
knott_version: 0.1.0
```

- Only `knott init` writes it. `validate` and `types` never write any file.
- A missing `config.yaml` is fine. A malformed one is a configuration error (exit `2`).
- v0 does not compare this version against the installed one. No migration framework.

### Entity discovery

Knott scans every `*.md` file under the vault root, recursively, with these rules:

- Skip any directory whose name starts with `.` (covers `.git`, `.knott`, `.obsidian`, …).
- Do not follow symlinked directories.
- `.gitignore` is not consulted in v0.
- Sort file paths so output is deterministic.

A file is an **entity** if it has YAML frontmatter that is a mapping containing a `type` key. All other Markdown files (no frontmatter, or frontmatter without `type`) are ordinary notes and are ignored silently.

---

## 4. Concept discovery

No schema registry or manifest in v0.

Each type is defined by one **concept file**, discovered from:

```
.knott/concepts/**/*.md
```

Each concept file defines exactly one entity type. Its YAML frontmatter is the type's schema (§7). Its body is an optional template for entity bodies (§7). Directory structure inside `.knott/concepts/` is purely organizational: `.knott/concepts/podcast/transcript.md` may define `name: transcript`.

The canonical identity of a type is the value of `name`, not the filename or path. Two concept files with the same `name` produce a validation error that names both files. Concept files use `name:` rather than `type:`, so no tool mistakes one for an entity, and `iter_markdown` never scans `.knott/` anyway.

Reserved:

- `.knott/schemas/` is the pre-0.5 layout. If it exists, a run reports one `schema-legacy-layout` issue and stops: no concept files are loaded and no entities are checked, so the one issue isn't buried under `entity-unknown-type`. `knott migrate` (§14) converts it.

Relation definitions are discovered the same way from `.knott/relations/**/*.md`, one relation per file, identified by `name` (§9).

See `docs/decisions/0010-concept-files-and-reference-properties.md`.

---

## 5. Entity model

Every knowledge object is a Markdown file with YAML frontmatter:

```markdown
---
type: transcript
title: Episode 42 transcript
created_at: 2026-10-06
generated_by: whisper
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
---
# Episode 42

Transcript content...
```

Conceptually:

```
frontmatter → structured metadata (properties: attributes and references)
body        → arbitrary Markdown, opaque to Knott in v0
```

Frontmatter parsing rules:

- Frontmatter starts with `---` on the first line (a UTF-8 BOM before it is tolerated) and ends at the next line that is exactly `---`. Both LF and CRLF line endings are accepted.
- A file that starts with `---` but has invalid YAML, or YAML that is not a mapping, is reported as an error (`entity-invalid-frontmatter`). Knott cannot tell whether it was meant to be an entity, so it does not skip it silently.

---

## 6. Entity type

Every entity has exactly one primary type, given by the reserved key `type`. Its value must be a string equal to the `name` of a discovered concept file.

No multiple types, no inheritance. Connections to other concepts are expressed through relations.

---

## 7. Concept file format

A concept file's frontmatter is the schema: the type's name, a human-readable description, and its properties. Its body is a template for entity bodies:

```markdown
---
name: transcript
description: >
  Transcript of recorded spoken content.
properties:
  title:
    type: string
    required: true
    description: Human-readable title.
  created_at:
    type: date
  derived_from:
    type: reference
    target: script
    description: >
      The source artifact from which this transcript was produced.
---
# <!-- The episode title. -->

<!-- One paragraph: who speaks and what it covers. -->
```

Allowed keys:

| Level | Key | Required | Notes |
|---|---|---|---|
| top | `name` | yes | matches `^[a-z][a-z0-9_-]*$` |
| top | `description` | no | string |
| top | `kid` | no | `required`: every entity of this type must have a `kid` (§12) |
| top | `properties` | no | mapping of property name → definition, in display order |
| property | `type` | yes | a scalar type in §8, or `list`, `object`, `map` or `reference` |
| property | `required` | no | boolean, default `false` |
| property | `description` | no | string |
| property | `items` | with `type: list` | the definition of each item (`type`, `description`, nesting keys; no `required`) |
| property | `fields` | with `type: object` | non-empty mapping of field name → definition |
| property | `values` | with `type: map` | the definition of each value (`type`, `description`, nesting keys; no `required`) |
| property | `target` | with `type: reference` | a type name, or a non-empty list of unique type names (self-reference allowed) |
| property | `relation` | no; `type: reference` only | the `name` of a relation definition (§9) |

Schema rules:

- Unknown keys in a concept file's frontmatter are errors. Knott owns these files, so a typo such as `propertes:` must not pass silently. Three keys get a targeted message: `type` ("concept files use `name:`") and `attributes` / `relations` ("merged into `properties`; run `knott migrate`").
- A file with no frontmatter is `schema-invalid-yaml`.
- Top-level property names must not be `type` or `kid`. Fields nested inside an `object` may be.
- `items`, `fields`, `values` and `target` are allowed only with their own `type`, and are required there.
- `relation` is allowed only on a reference definition (§9); on a `list` or `map`, the error says to put it on `items` or `values`.
- A property whose shape is `reference`, at any depth, is a **relation** (§9–11). Every other property is an **attribute** (§8). They share one map, so a name can't be both.

### Body template

Everything after the closing `---` is the type's template, stored verbatim (`None` when blank). Agents, and later a `knott new` command, copy it when they create an entity. Knott never checks an entity's body against it. There is no placeholder syntax: write the sections as real headings, with a `<!-- … -->` comment under each that says what goes there. A heading whose text varies, such as the H1, holds a comment as its text. Comments stay out of Obsidian's reading view.

Concept files serve three purposes:

1. A machine-readable validation contract.
2. Human-readable semantic documentation.
3. Context an AI agent reads, and a body it copies, before creating or modifying entities.

---

## 8. Attributes

Attributes are properties whose values belong to the entity itself: every property that isn't a reference.

Scalar types and accepted YAML values (strict typing, no coercion beyond what's listed here):

| Type | Accepts | Rejects |
|---|---|---|
| `string` | YAML strings | numbers, booleans, dates (e.g. unquoted `42`, `no`, `2026-10-06`) |
| `integer` | YAML integers | booleans, floats |
| `number` | YAML integers and floats | booleans |
| `boolean` | `true` / `false` | everything else |
| `date` | YAML date (`2026-10-06`) or a string in ISO 8601 date form | datetimes |
| `datetime` | YAML timestamp or a string in ISO 8601 datetime form | plain dates |

Notes for implementers:

- In Python, `bool` is a subclass of `int` and `datetime` is a subclass of `date`. Check the exact type.
- PyYAML uses YAML 1.1, so unquoted `yes`, `no`, `on` and `off` parse as booleans. The error for a `string` field that holds a boolean should suggest quoting the value.

Rules:

- A key that is present with a `null` or empty value counts as absent.
- `required: true` means the key is present and not null.

### Structured attributes

A property can also be a `list` (every item matches `items`), an `object` (exactly the declared `fields`; objects are closed) or a `map` (free string keys; every value matches `values`). Shapes nest to any depth:

```yaml
properties:
  senses:
    type: list
    required: true
    items:
      type: object
      fields:
        id: {type: string, required: true}
        ru: {type: string, required: true}
  forms:
    type: map
    values:
      type: map
      values: {type: string}
```

- Every nested value is checked against its definition. Problems give the full path in `field` (`senses[1].ru`, `forms.sg.acc`) and the nested line.
- An empty container of the declared kind (`[]` for a list, `{}` for an object or map) counts as absent, so a required list needs at least one item. An empty container of another kind is a type mismatch. List items and map values are never absent.
- An undeclared key in an object is `attribute-unknown-field`. A non-string map key is a type mismatch.
- A value of the wrong kind is reported once, without checking its contents.

See `docs/decisions/0008-structured-attributes.md`.

A `reference` (§9) may appear anywhere a shape can: list `items`, map `values`, or an object field.

Not in v0: enums, unions of scalar types, item counts, named reusable shapes, custom scalars, inheritance, composition.

---

## 9. Relations

A relation is a semantic, directed reference from one entity to another:

```
transcript ── derived_from ──▶ script
```

Relations are properties of the **source** type (§7) whose shape is `reference`:

```yaml
properties:
  derived_from: { type: reference, target: script }
  recording_of: { type: reference, target: [episode, meeting] }
  sources:
    type: list
    items: { type: reference, target: script }
  speakers:
    type: list
    items:
      type: object
      fields:
        person: { type: reference, target: person }
```

- A `reference` shape can appear at the top level, as list `items`, as map `values`, or as an object field, at any depth.
- `target` is one type name or a list of them. An entity of any listed type passes.
- Only keys declared with a reference shape are relations. An undeclared key whose value looks like a path or link is ordinary metadata and is never checked, whatever its name.

### Relation definitions

A relation definition says what a link means, once, for every property that uses it: its name read from the target side (`inverse`), whether it goes both ways (`symmetric`), and whether it may loop (`acyclic`). Each is one Markdown file, discovered from `.knott/relations/**/*.md` (subfolders are only for organisation; other file types are ignored):

```markdown
---
name: supersedes
inverse: superseded_by
acyclic: true
description: This entity replaces the target. The target stays as history.
---
<!-- Use when the old entity is no longer the current answer. For a partial change, use `amends`. -->
```

The frontmatter is the definition. The body is optional usage guidance, stored verbatim (`None` when blank), shown by `types --verbose` and `view`, and never checked against anything. Keys are closed:

| Key | Required | Value |
|---|---|---|
| `name` | yes | `^[a-z][a-z0-9_-]*$`. Relation names and concept names are separate namespaces. |
| `description` | no | string |
| `inverse` | no | a name, same pattern as `name` |
| `symmetric` | no | `true` / `false` (strict spelling), default `false` |
| `acyclic` | no | `true` / `false`, default `false` |

- `transitive` is reserved: `schema-invalid-field` ("reserved, not supported yet"). Any other key is `schema-invalid-field` with a "did you mean" suggestion. A file with a valid `name` is still registered when an optional key is invalid; that key is dropped.
- A file with no frontmatter, or invalid YAML, is `schema-invalid-yaml`. Two files with the same `name` are `schema-duplicate-relation`, reported at the second file in path order and naming both.
- A relation no property names is valid, and is listed by `types --verbose`.

A reference property names a relation with `relation:`:

```yaml
properties:
  supersedes: { type: reference, target: decision, relation: supersedes }
  affects:
    type: list
    items: { type: reference, target: concept, relation: about }
```

- `relation:` is allowed on a `reference` shape only, at any depth. On a `list` or `map` it is `schema-invalid-field` with "put `relation:` on `items`" (or `values`); on another shape, "only allowed when `type` is reference". Its value must be a string.
- The property keeps its own `target`, `required` and `description`. The relation declares no source or target types and never adds a key to a concept.
- A name no relation file defines is `relation-unknown`, at the `relation:` line. The reference still works as a plain reference.
- Many properties may name one relation, in one concept or across concepts, under any key names.

### Checks on definitions

Run on every command, after all concept and relation files are read. Only known targets are considered.

| Rule | Code | Reported at |
|---|---|---|
| Two relations declare the same `inverse` | `relation-inverse-conflict` | the second file's `inverse:` line, naming both |
| An `inverse` equals another relation's `name` | `relation-inverse-conflict` | the `inverse:` line |
| An `inverse` equals its own `name` | `relation-inverse-conflict`, suggesting `symmetric: true` | the `inverse:` line |
| An `inverse` equals a top-level property name of a concept that a property naming this relation can target | `relation-inverse-conflict`, naming the concept | the `inverse:` line, one issue per concept |
| `symmetric: true` with an `inverse` | `relation-symmetric-mismatch` | the `inverse:` line |
| `symmetric: true` with `acyclic: true` | `relation-symmetric-mismatch` | the `acyclic:` line |
| A property names a symmetric relation, but its known targets don't include the property's own concept | `relation-symmetric-mismatch` | the concept file's `relation:` line |

A nested field name (`speakers[].role`) never conflicts with an `inverse`, and neither does a property of a concept the relation's properties can't target.

### Cycles

For each relation with `acyclic: true` (and not `symmetric`) that some property names, knott builds one graph from the whole vault, lazily, once per run:

- Nodes are entities. Edges are references at properties that name the relation, at any depth, in any concept, that pass every check in §11, including the target-type check. Path and `kid:` references count the same. Entities with invalid frontmatter or an unknown type add no edges.
- Each strongly connected component with more than one entity, or an entity that references itself, is one `relation-cycle` issue. Loops mixing two relations are not reported.
- The message names the shortest loop from the component's entity with the smallest path (successors tried in path order): "`supersedes` must not form a cycle: decisions/0011.md → decisions/0012.md → decisions/0011.md". It is reported at the first entity on that loop, in path order, that is in the run's scope, at the line of its reference to the next entity (the first in schema order when there are several); `field` is that property's full path.
- A scoped run reports a cycle when at least one entity of its component is in scope. If none of the named loop's entities is, the loop is taken from the component's smallest in-scope entity and reported there.

See `docs/specs/0006-relation-definitions.md`.

---

## 10. Relation storage

Relations are stored only on the source side. The script does not get an inverse `derived_from`. This avoids duplicated state, sync problems, and unclear ownership of a relation.

Reverse navigation is computed, never stored: `knott refs` (§14) and `Knott.refs()` (§21), or Obsidian backlinks. A relation's `inverse` (§9) is a label for reading the link from the target side, not a property.

### Reverse lookup

Reverse lookup collects, for one entity E, every reference in the vault that resolves to E. Only declared reference properties count. A reference that resolves to E but fails the target-type check is still listed, because it still points at E; `validate` reports the mismatch separately.

References are grouped by a **label**:

| The referring property | Group label | Kind |
|---|---|---|
| names a relation with an `inverse` | the inverse, e.g. `superseded_by` | `inverse` |
| names a symmetric relation | the relation's name, e.g. `related` | `symmetric` |
| names a relation without `inverse`, not symmetric | `← <name>`, e.g. `← about` | `relation` |
| names no relation, or an unknown one | `← <type>.<path>`, e.g. `← guide.concepts[]` (path notation as in `references()`) | `property` |

- Properties from different concepts that name the same relation share one group.
- Symmetric groups also include E's own outgoing references at properties naming that relation. Each linked entity appears once, with direction `in` (only the other side stores it), `out` (only E stores it) or `both`. Storing a symmetric link on both sides is valid and is never reported. `field` and `line` say where the link is stored: the linked entity's (first, in schema order) reference for `in` and `both`, E's own for `out`. A self-reference at a symmetric property is `both`.
- A relation that is both `symmetric` and has an `inverse` is grouped by its inverse. Two relations that declare the same `inverse` give two groups with the same label, one per relation.
- Groups are ordered: `inverse`, `symmetric` and `relation` groups by label (then relation name), then `property` groups by label. Within a group, references are ordered by source path, then field in schema order (list items in list order); symmetric groups by linked entity's path.

---

## 11. Relation references

Relations use **relative filesystem paths** by default. A reference may also name an entity by its `kid` (§12).

### Value shape

Cardinality is strict. `type: reference` holds exactly one reference. Several is `type: list` with reference `items`:

```yaml
# reference: one, plain path
derived_from: ../scripts/episode-42.md
```

```yaml
# reference: one, Markdown link
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
```

```yaml
# list of reference
sources:
  - ../scripts/episode-42.md
  - "[Notes](../notes/episode-42-notes.md)"
```

| Value | `reference` | `list` of `reference` |
|---|---|---|
| `null` / `""` | absent | absent |
| `[]` | `relation-invalid-value` | absent |
| `{}` | `relation-invalid-value` | `relation-invalid-value` |
| string | resolved | `relation-invalid-value` ("write it as a list of references, even for one") |
| list | `relation-invalid-value` ("declare `type: list` with reference `items` for several") | each item resolved; a null or empty item is `relation-invalid-value` |

A `required: true` reference that is absent is `relation-missing`, and so is a required list or map of references. `required: true` on a list means at least one item. Obsidian templates often leave properties blank, which is why `null` and `""` count as absent.

Each reference is a string in one of two forms:

1. **Plain path**: `../scripts/episode-42.md`
2. **Markdown link**: `[label](../scripts/episode-42.md)`. Knott ignores the label. The destination may be wrapped in `<…>` and may be percent-encoded (`%20`). It must be quoted in YAML.

The Markdown-link form is the recommended one for vaults opened in Obsidian. Since Obsidian 1.11, Markdown links in text and list properties are clickable and are updated when the target is moved or renamed. Plain paths are not clickable in Obsidian. Wikilinks (`[[…]]`) are not supported in v0, because they resolve by note name rather than by relative path.

For vaults edited in Obsidian, document these settings:

- Files & links → *New link format*: **Relative path to file**
- *Use [[Wikilinks]]*: **off**

With other settings, Obsidian may rewrite links on rename into forms that `knott validate` rejects. That is the intended safety net.

### Resolution and checks

Each reference is resolved relative to the directory of the file containing it. Each step must pass, and each failure is reported separately:

```
value has the declared shape (table above)        → relation-invalid-value
  (an unquoted [[x]] parses as a nested list and fails here; the error
   suggests quoting the value)
reference parses as a plain path or Markdown link → relation-invalid-value
  (URL schemes, #fragments, absolute paths, and destinations not ending
   in .md are rejected here)
resolved path stays inside the vault root          → relation-target-outside-vault
target exists, with exact case matching            → relation-target-not-found
target is a Knott entity                           → relation-target-not-entity
target's type is in the property's target list     → relation-target-type-mismatch
```

A reference written `kid:<uuid>` skips the path steps. It must be a canonical lowercase UUID (`relation-invalid-value`; a `[label](kid:…)` link is rejected too), exactly one entity must have that `kid` (`relation-target-not-found`, or `relation-target-ambiguous` when several do), and then the type check runs as above.

Use exact case matching so results are the same on case-insensitive filesystems (macOS) and case-sensitive ones (Linux).

An unquoted `[label](path)` is not valid YAML, so it surfaces as `entity-invalid-frontmatter`. That error should also suggest quoting the value when the failing line looks like a Markdown link.

Issues give the full path in `field` (`speakers[1].person`, `sources[0]`) and the line of the nested key or item. A type-mismatch message names every allowed type (``expects target type `episode` or `meeting` ``).

---

## 12. Stable identity: `kid`

Every entity may carry a knott-managed identity that survives moves and renames:

```yaml
type: lexeme
kid: 3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21
```

- `kid` is a reserved top-level key, like `type`. Its value is a canonical lowercase UUID (any version; knott generates v4). Other spellings are `kid-invalid`, and the message gives the canonical form.
- It is optional unless the concept file says `kid: required` (`kid-missing`).
- It is unique across the vault, whatever the type. A duplicate is reported once (`kid-duplicate`), on the first claimant by path, naming every claimant. A scoped run reports a duplicate only if one of its claimants is in scope.
- `knott validate --fix` inserts `kid: <uuid4>` into every in-scope entity without a `kid` key: one line, after `type:` (or before the closing `---`), with the rest of the file unchanged, re-parsed before it is written. It never changes an existing `kid`, including duplicates. This is knott's only edit to user files.
- References may name an entity as `kid:<uuid>` (§11), at any depth. Markdown links remain the default.
- Resolution stays behind `resolve_reference()` in `vault/links.py`. The `kid` index is built once per run, only when a run needs it. Within a run, each reference is resolved once and each directory is listed once for the exact-case check; nothing is kept between runs.

A `kid` does not detect two entities describing the same concept. See `docs/decisions/0009-kid-identity.md`.

---

## 13. Validation

Validation is the primary feature of v0. A run loads all concept files, then validates entities. If `.knott/schemas/` exists, the run reports only `schema-legacy-layout` (§4).

### Schema validation

- Each concept file has frontmatter, which is valid YAML and a mapping.
- `name` is present and well-formed. No unknown keys (§7).
- Each property has a known `type`; `list`, `object`, `map` and `reference` have their nested key, recursively valid.
- Each name in a reference's `target` names a discovered type (`schema-unknown-target`, one issue per unknown name, `field` = the full key path such as `properties.sources.items.target`). Unknown names are dropped from the target list. If none is left, values are still checked for shape and resolved, but the target-type check is skipped.
- `kid`, when present, is `required`.
- No duplicate `name` across files (`schema-duplicate-type`).
- No top-level property named `type` or `kid`.
- Relation files are well-formed, with unique names (`schema-duplicate-relation`); every `relation:` names one (`relation-unknown`); the checks on definitions pass (`relation-inverse-conflict`, `relation-symmetric-mismatch`; §9).

### Entity validation

- `type` is the `name` of a discovered concept file (`entity-unknown-type`).
- `kid`: present when the schema requires it (`kid-missing`), a canonical UUID (`kid-invalid`), and unique (`kid-duplicate`).
- Attributes: required ones are present (`attribute-missing`) and values match their type (`attribute-type-mismatch`), at every nesting level. Declared objects have no undeclared keys (`attribute-unknown-field`).
- References, at every nesting level: checked as in §11. A list or map whose items are references uses the `relation-*` codes.
- No relation with `acyclic: true` forms a loop (`relation-cycle`, §9).
- Undeclared top-level keys are allowed and not checked. Strict schemas may come later.

For example, this stays valid even though `some_personal_metadata` is not in the schema:

```yaml
type: transcript
title: Episode 42
created_at: 2026-10-06
some_personal_metadata: foo
```

### Scope of a run

- `knott validate` (no args) checks every concept file and every entity.
- `knott validate PATH...` always checks every concept file, because entity checks depend on them. Entity checks cover only the given files, or the entities under the given directories. Relation targets outside those paths are still read to check their type.
- An explicitly given file that is not an entity is an error (`not-an-entity`).

---

## 14. CLI

Keep the CLI deliberately small:

```
knott init [PATH]
knott validate [PATH...] [--fix]
knott types [--verbose]
knott migrate [PATH]
knott version
knott skill install [PATH]
knott view [PATH]
knott refs PATH
```

### `knott init [PATH]`

Creates `.knott/concepts/` and `.knott/config.yaml` in `PATH` (default: cwd). No content directories and no concept files.

If `.knott/` already exists, it changes nothing, prints that the vault is already initialized, and exits with code `0`.

### `knott validate [PATH...]`

See §13 for scope and §20 for output. `--fix` first gives a `kid` to every in-scope entity that has none (§12), prints `+ kid  <path>` for each, then validates. With `--format json`, the output gains `"fixed": [{path, kid}]`.

### `knott types`

Prints discovered type names, one per line, sorted:

```
feedback
script
transcript
```

If schema errors exist, `types` still prints the types it could load, writes the errors to stderr, and exits with code `1`.

`--verbose` adds, per type: the concept file path, the description, `kid: required` when set, `template: yes|no`, `references:` with the path of every reference at any depth (`[]` for list items, `.*` for map values, `.field` for object fields, or `none`), and the properties with nested shapes indented. A reference shows `→ target | target`; a target no concept defines is marked `(unknown)`. A reference that names a relation shows it after the type, as part of the type column: `affects  list of reference → concept  (about)`; a name no relation file defines is not shown.

After the types, a `relations:` section lists every relation, sorted by name: on one line, indented by two spaces, the name, then `inverse: <x>`, `symmetric`, `acyclic` as they apply, separated by two spaces; then the description and the guidance, each line indented by four spaces (blank lines kept empty). Relations are separated by a blank line. A vault without relations has no `relations:` section. From `tests/fixtures/relation-refs`:

```
relations:
  about  inverse: discussed_in
    The source discusses the target.

  cites

  related  symmetric
    The two entities are worth reading together.
    Store the link on either side.

  supersedes  inverse: superseded_by  acyclic
    This entity replaces the target.
    <!-- Use when the old entity is no longer the current answer. -->

    For a partial change, use `amends`.
```

### `knott migrate [PATH]`

Converts a pre-0.5 vault. Reads every `.knott/schemas/**/*.yaml` with the safe loader (the parser limits of decision 0007 apply) and writes `.knott/concepts/<same relative path>.md`:

- `type` → `name`; `description` and `kid` are kept.
- `attributes`, then `relations`, merge into `properties`, in file order.
- A relation becomes `{type: reference, target, description}`, or `{type: list, required, description, items: {type: reference, target}}` when any entity of that type stores a list in that field.
- Output is block-style YAML in source key order; multi-line descriptions are folded (`>`). The body is empty.

It refuses (exit `2`, nothing written) when there is no `.knott/schemas/`; a legacy file is unreadable, not UTF-8, not valid YAML, has unknown keys, or declares a name as both attribute and relation; a target `.md` already exists, or a non-folder sits where one of its folders would go; `.knott/schemas/` is a symbolic link; or `.knott/schemas/` holds a non-hidden file that isn't `.yaml` (the folder is deleted afterwards). If writing a concept file fails (`OSError`), the files and folders written so far are removed and it exits `2` with nothing changed. If only deleting `.knott/schemas/` fails, the written concept files are kept (the delete may have removed legacy files already) and it exits `2`, asking the user to delete the folder by hand. On success it writes every file, deletes `.knott/schemas/`, then validates and prints:

```
+ .knott/concepts/compilation.md
+ .knott/concepts/script.md
  list of reference: compilation.sources
- .knott/schemas/

<the validate output>
```

The exit code is the validation exit code. `migrate` writes only inside `.knott/`, knott's own configuration, so it never edits entities.

### `knott version`

Prints the installed Knott version.

### `knott view [PATH] [-o FILE] [--no-open]`

Writes the vault's ontology (types, properties, templates, references, entity counts) as one self-contained static HTML page and opens it in the browser. No server and no network. Each reference is an edge per known target, labelled with its path; it is drawn as required only when every step on its path is required. Targets no concept defines get no edge and are marked `(unknown)` in the type's panel. A reference that names a relation is labelled with the relation's name instead of its path; the type's panel shows the path with the relation in parentheses under "References out", and, under "Referenced by", every reference property (any depth, any type, T included) whose known targets include the type, grouped and labelled as in reverse lookup (§10), each row `<source type>.<property path>`. A "Relations (N)" button in the header, hidden without relations, lists every relation with its keys, description and guidance (HTML-escaped). The embedded data has `relations`, a `relation` key on each edge, and `referenced_by`: a list of `{type, groups}`, each group `{label, kind, relation, references: [{type, path, required}]}`. Schema errors still produce a page, with a note to run `knott validate`; a vault that still has `.knott/schemas/` prints the `schema-legacy-layout` issue to stderr, writes no page and exits `1`; a vault with no types exits with code `2`. See `docs/commands/view.md`.

### `knott refs PATH [--format text|json]`

Lists every reference that points at one entity (reverse lookup, §10). `PATH` is an entity file (relative to the current directory) or `kid:<uuid>`. The vault is found from PATH's location, or from the current directory for `kid:`.

```
$ cd docs && knott refs concepts/kid.md
concepts/kid.md  concept

discussed_in
  decisions/0009-kid-identity.md  decision    affects[0]
  issues/kid-duplicate.md         issue_code  about
  issues/kid-invalid.md           issue_code  about
  issues/kid-missing.md           issue_code  about

related
  concepts/entity.md                concept  related[0]  →
  concepts/reference-resolution.md  concept  related[1]  →
  concepts/schema.md                concept  related[2]  →

← spec.concepts[]
  specs/0004-kid-identity.md  spec  concepts[0]
```

- The header line is the entity's vault-relative path, two spaces, and its type. Each group is preceded by a blank line, then its label, then one line per reference indented by two spaces: path, type, field, and, in symmetric groups, the direction `←` (in), `→` (out) or `⇄` (both). Within a group, every column but the last is padded to the group's widest value plus two spaces; lines have no trailing spaces.
- An entity nobody references prints its header line, a blank line and `no references`.
- `--format json` prints `{"entity": {path, type, kid}, "groups": [{label, kind, relation, references: [{path, type, kid, field, line, direction}]}]}`. `relation` is `null` for `property` groups; `direction` is always `in` outside symmetric groups.
- `refs` does not validate. Schema issues don't stop it; it works with the concepts and relations that loaded.
- Exit codes: `0` on success, including no references. `1` when the vault has the legacy layout (`schema-legacy-layout` on stderr). `2` when PATH doesn't exist, isn't inside the vault, isn't an entity (a file under `.knott/` or another hidden folder, a folder, a note without `type`, a file whose frontmatter can't be read), or a `kid:` is malformed or matches no entity or several.

---

## 15. Authoring

Knott does not own entity authoring in v0. An agent or human creates a Markdown file directly and runs:

```sh
knott validate path/to/file.md
```

Not in v0: `knott create`, `knott edit`, `knott link`.

---

## 16. Agent skill

Ship an agent instruction document in the repo at `src/knott/_skills/knott/SKILL.md`, in Agent Skills format (frontmatter with `name` and `description`). It explains:

- what a Knott vault is, and that Markdown is the source of truth
- where concept files live, how to read them, and how to use the body template
- how to discover types (`knott types`)
- how to create an entity and write references (relative paths, Markdown-link form, quoted; strict cardinality; nested references)
- that `knott validate <file>` must be run after every change
- relation files: how to read their guidance, never to write an inverse, `knott refs` before renaming or deleting, and `relation-cycle`

Typical agent workflow:

1. Run `knott types --verbose` and look in `.knott/concepts/`.
2. Pick the relevant type and read its concept file.
3. Create or update the Markdown entity, starting a new body from the concept's template.
4. Write references as relative paths, one value for a `reference` and a list for a `list` of references.
5. Run `knott validate <file>`.
6. Fix every reported issue before finishing.

The skill describes usage. The CLI provides deterministic behavior.

---

## 17. Indexing and search

Out of scope for v0. No SQLite, FTS, vector DBs, embeddings, graph DBs, RDF stores, persistent or background indexes.

The reference index behind cycles and reverse lookup (§9, §10) lives in memory for one run and is never written.

Any future index must be derived, disposable, and fully rebuildable from the files:

```
Markdown files → rebuildable derived index → search / traversal / retrieval
```

---

## 18. Semantic model

Knott borrows vocabulary from RDF (entity, attribute, relation/predicate, schema) but does not implement RDF. Relation definitions (§9) name a link's inverse and mark it symmetric or acyclic; inverses are labels for reverse lookup, never stored or inferred. Not in v0: RDF serialization, RDFS, OWL, SPARQL, reasoning, inference, transitive relations (`transitive` is reserved), domain and range on relations, cardinality constraints beyond `required` and `reference` vs `list`.

The model must stay small enough to understand by reading a few concept files.

---

## 19. Versioning

- Knott follows SemVer (`0.1.0`, `0.2.0`, …).
- The vault records `knott_version` at init (§3).
- Schemas have no version field; Git holds their history.
- If the storage format ever needs independent versioning, add `format_version` then. Do not conflate package and format versions.

---

## 20. Output and errors

Errors must be useful to humans and agents: deterministic, readable, actionable.

Every issue has:

| Field | Meaning |
|---|---|
| `code` | stable kebab-case identifier (list below) |
| `path` | vault-relative path of the file with the problem |
| `line` | 1-based line in that file, when known |
| `field` | frontmatter or schema key, when applicable |
| `message` | human-readable explanation, including expected vs actual |

Line numbers come from PyYAML's `compose()` node marks. If a line can't be determined, omit it rather than guess.

Text output format:

```
✗ transcripts/foo.md:4  derived_from
  relation `derived_from` expects target type `script`
  but `../scripts/foo.md` has type `feedback`

1 validation error
```

Issues are sorted by path, then line.

Success output:

```
✓ 2 schemas
✓ 2 entities
✓ 1 relation
✓ vault is valid
```

"Relations" counts each resolved reference, so a list of three counts as 3.

### Issue codes

```
schema-invalid-yaml        schema-invalid-field       schema-duplicate-type
schema-unknown-target      schema-legacy-layout       schema-duplicate-relation
relation-unknown           relation-inverse-conflict  relation-symmetric-mismatch
entity-invalid-frontmatter entity-unknown-type        not-an-entity
kid-missing                kid-invalid                kid-duplicate
attribute-missing          attribute-type-mismatch    attribute-unknown-field
relation-missing           relation-invalid-value     relation-target-outside-vault
relation-target-not-found  relation-target-not-entity relation-target-type-mismatch
relation-target-ambiguous  relation-cycle
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | success / valid |
| `1` | one or more validation issues (schema or entity) |
| `2` | usage error, no vault found, unreadable or malformed `.knott/config.yaml`, or a path argument that doesn't exist |

---

## 21. Python API

Core behavior is available independently of the CLI, and the CLI is a thin adapter over it:

```python
from knott import Knott

vault = Knott.open(".")            # walks up to the vault root; raises VaultNotFoundError
result = vault.validate()          # or vault.validate(["transcripts/foo.md"])
result.ok                          # bool
result.issues                      # list[Issue], sorted
result.stats                       # schemas / entities / relations counts
vault.validate(fix=True)           # add missing kids first; result.fixed lists them
types = vault.types()              # list[str], sorted
ontology = vault.ontology()        # Ontology: types with properties, templates, counts, relations
ontology.types[0].references()     # [("speakers[].person", OntologyAttribute), …]
ontology.relations                 # [RelationDefinition(name, description, inverse, symmetric,
                                   #   acyclic, guidance, path), …], sorted by name
refs = vault.refs("concepts/kid.md")   # or "kid:<uuid>"; Refs(entity, groups), see §10
vault.migrate()                    # MigrateResult(written, removed, list_fields); see §14
```

`OntologyAttribute.relation` is the relation a reference names (`None` when none, or one no relation file defines). `Refs` has `entity: EntityRef(path, type, kid)` and `groups: list[RefGroup(label, kind, relation, references: list[Ref(path, type, kid, field, line, direction)])]`; `type` is the frontmatter `type` as written. A relative path passed to `refs()` is resolved against the vault root, as in `validate()`.

`validate()` returns validation problems as data and never raises for them. It raises only for `2`-class conditions (`KnottError` subclasses in `errors.py`).

---

## 22. Testing

Write behavior and contract tests, not tests of implementation details. Each fixture vault describes external behavior:

```
tests/fixtures/
├── valid-vault/                    # includes plain Markdown notes that must be ignored
├── unknown-type/
├── missing-required-field/
├── wrong-attribute-type/           # incl. bool-as-int, datetime-as-date, unquoted `no`
├── invalid-frontmatter/
├── missing-relation-target/
├── wrong-relation-target-type/
├── relation-outside-vault/
├── relation-markdown-link/         # Markdown-link, <…>, and %20 forms
├── relation-list/
├── unknown-relation-target-type/   # schema references a type that doesn't exist
├── nested-references/              # references inside lists, maps and objects
├── union-target/                   # target: [a, b], partly or wholly unknown
├── reference-cardinality/          # reference vs list of reference
├── legacy-layout/                  # .knott/schemas/ for knott migrate
├── duplicate-schema-type/
├── schema-unknown-key/
├── relation-definitions/           # .knott/relations/ and relation: on references
├── relation-cycles/                # acyclic relations: self-loop, pairs, chains, kid edges
└── relation-refs/                  # knott refs: every group kind and direction
```

At minimum, test: schema discovery and parsing, entity detection, attribute typing, relation parsing and resolution, target type checks, duplicate schema handling, the CLI output format, and exit codes.

---

## 23. Explicitly out of scope

Do not add, unless needed purely to meet the requirements above:

database as source of truth · search indexes · semantic or vector search · embeddings · automatic inverse relations · global relation registry · RDF / OWL · inference or reasoning · schema inheritance, composition, or versioning · migration framework (`knott migrate` is a one-off converter for decision 0010) · UI (an interactive or served app; the static page `knott view` writes is not one) · HTTP server · daemon · filesystem watcher · automatic knowledge extraction · automatic memory selection · agent deciding autonomously what to persist · plugin architecture · wikilink resolution.

Avoid speculative abstractions. Prefer the smallest implementation that satisfies the contract.

---

## 24. Definition of Done

Given `.knott/concepts/script.md`:

```markdown
---
name: script
properties:
  title:
    type: string
    required: true
---
```

and `.knott/concepts/transcript.md`:

```markdown
---
name: transcript
properties:
  title:
    type: string
  derived_from:
    type: reference
    target: script
    description: >
      The script from which this transcript was produced.
---
```

and `scripts/foo.md`:

```markdown
---
type: script
title: Episode 42
---
# Episode 42
```

and `transcripts/foo.md`:

```markdown
---
type: transcript
title: Episode 42 transcript
derived_from: "[Episode 42](../scripts/foo.md)"
---
# Transcript
```

then `knott validate` exits `0` and prints:

```
✓ 2 schemas
✓ 2 entities
✓ 1 relation
✓ vault is valid
```

The same holds when `derived_from` is the plain path `../scripts/foo.md`.

If `scripts/foo.md` changes to `type: feedback` (with a `feedback` schema present), `knott validate` exits `1` and prints:

```
✗ transcripts/foo.md:4  derived_from
  relation `derived_from` expects target type `script`
  but `../scripts/foo.md` has type `feedback`

1 validation error
```

Also: `uvx knott version` works from a built wheel, and `src/knott/_skills/knott/SKILL.md` exists.

---

## 25. Core design principle

When a choice is ambiguous, keep this invariant:

> The files should remain obvious to a human, while Knott adds machine-verifiable semantics on top.

The whole useful v0 path is:

```
discover concept files → parse Markdown + frontmatter → validate attributes → resolve and validate references
```

Do not build beyond it unless this spec requires it.

---

## 26. Proposed additions (not required for v0; accept or drop)

These are cheap and fit the agent-first goal, but they add scope:

- `knott validate --format json`: emits `{ok, stats, issues[]}` using the issue fields from §20. Agents should not have to parse text output.
- `knott types --verbose`: prints each type's `description`, concept file path, references and properties, so an agent can go straight to the right file.
- `knott skill`: prints the bundled `SKILL.md`, so agents installed through `uvx` can find it without the repo.
