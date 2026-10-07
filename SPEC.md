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
    loader.py
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
│   └── schemas/
│       ├── script.yaml
│       ├── transcript.yaml
│       └── feedback.yaml
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

## 4. Schema discovery

No schema registry or manifest in v0.

Schemas are discovered from:

```
.knott/schemas/**/*.yaml
```

(`.yml` is not recognized in v0.)

Each schema file defines exactly one entity type. Directory structure inside `.knott/schemas/` is purely organizational. `.knott/schemas/podcast/transcript.yaml` may define `type: transcript`.

The canonical identity of a type is the value of `type`, not the filename or path. Two schema files defining the same `type` produce a validation error that names both files.

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
frontmatter → structured metadata (attributes + relations)
body        → arbitrary Markdown, opaque to Knott in v0
```

Frontmatter parsing rules:

- Frontmatter starts with `---` on the first line (a UTF-8 BOM before it is tolerated) and ends at the next line that is exactly `---`. Both LF and CRLF line endings are accepted.
- A file that starts with `---` but has invalid YAML, or YAML that is not a mapping, is reported as an error (`entity-invalid-frontmatter`). Knott cannot tell whether it was meant to be an entity, so it does not skip it silently.

---

## 6. Entity type

Every entity has exactly one primary type, given by the reserved key `type`. Its value must be a string naming a discovered schema.

No multiple types, no inheritance. Connections to other concepts are expressed through relations.

---

## 7. Schema format

A schema describes the entity type, a human-readable description, attributes, and relations:

```yaml
type: transcript
description: >
  Transcript of recorded spoken content.
attributes:
  title:
    type: string
    required: true
    description: Human-readable title.
  created_at:
    type: date
  generated_by:
    type: string
relations:
  derived_from:
    target: script
    required: false
    description: >
      The source artifact from which this transcript was produced.
```

Allowed keys:

| Level | Key | Required | Notes |
|---|---|---|---|
| top | `type` | yes | matches `^[a-z][a-z0-9_-]*$` |
| top | `description` | no | string |
| top | `attributes` | no | mapping of field name → attribute definition |
| top | `relations` | no | mapping of field name → relation definition |
| attribute | `type` | yes | one of the scalar types in §8 |
| attribute | `required` | no | boolean, default `false` |
| attribute | `description` | no | string |
| relation | `target` | yes | an existing schema `type` (self-reference allowed) |
| relation | `required` | no | boolean, default `false` |
| relation | `description` | no | string |

Schema rules:

- Unknown keys in a schema file are errors. Knott owns these files, so a typo such as `atributes:` must not pass silently.
- Field names must not be `type`.
- A field name cannot be both an attribute and a relation in the same schema.

Schemas serve three purposes:

1. A machine-readable validation contract.
2. Human-readable semantic documentation.
3. Context an AI agent reads before creating or modifying entities.

---

## 8. Attributes

Attributes are values that belong to the entity itself.

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

Not in v0: enums, unions, lists, nested objects, custom scalars, inheritance, composition.

---

## 9. Relations

A relation is a semantic, directed reference from one entity to another:

```
transcript ── derived_from ──▶ script
```

Relations are declared in the schema of the **source** type (§7). There is no global relation registry.

Only keys declared under `relations` in the source schema are relations. An undeclared key whose value looks like a path or link is ordinary metadata and is never checked as a relation.

---

## 10. Relation storage

Relations are stored only on the source side. The script does not get an inverse `derived_from`. This avoids duplicated state, sync problems, and unclear ownership of a relation.

Reverse navigation is left to tools: Obsidian backlinks, or a future derived index (§17). Explicit inverse relations may come later if real workflows need them.

---

## 11. Relation references

In v0, relations use **relative filesystem paths**, not Knott IDs.

### Value shape

A relation value is either one reference or a list of references:

```yaml
# a single reference, plain path
derived_from: ../scripts/episode-42.md
```

```yaml
# a single reference, Markdown link
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
```

```yaml
# a list of references
sources:
  - ../scripts/episode-42.md
  - "[Notes](../notes/episode-42-notes.md)"
```

A `null`, empty, or `[]` value counts as absent, the same as for attributes. Obsidian templates often leave properties blank.

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
value is a string or a list of strings            → relation-invalid-value
  (an unquoted [[x]] parses as a nested list and fails here; the error
   suggests quoting the value)
reference parses as a plain path or Markdown link → relation-invalid-value
  (URL schemes, #fragments, absolute paths, and destinations not ending
   in .md are rejected here)
resolved path stays inside the vault root          → relation-target-outside-vault
target exists, with exact case matching            → relation-target-not-found
target is a Knott entity                           → relation-target-not-entity
target's type equals relation.target               → relation-target-type-mismatch
```

Use exact case matching so results are the same on case-insensitive filesystems (macOS) and case-sensitive ones (Linux).

An unquoted `[label](path)` is not valid YAML, so it surfaces as `entity-invalid-frontmatter`. That error should also suggest quoting the value when the failing line looks like a Markdown link.

If the schema marks a relation `required: true`, the key must be present with at least one reference (`relation-missing`).

---

## 12. Stable IDs

Out of scope for v0. Paths are human-readable, inspectable, clickable, and Git-friendly.

The design should not block a later

```yaml
id: some-stable-id
```

with a `path ↔ id` mapping. Concretely: keep relation resolution in one module (`vault/links.py`) behind a single function. Build no ID infrastructure now.

---

## 13. Validation

Validation is the primary feature of v0. A run loads all schemas, then validates entities.

### Schema validation

- Each schema file is valid YAML and a mapping.
- `type` is present and well-formed. No unknown keys (§7).
- Each attribute has a known scalar `type`.
- Each relation `target` names a discovered type.
- No duplicate `type` across files.
- No field name collisions, and no field named `type`.

### Entity validation

- `type` names a discovered schema (`entity-unknown-type`).
- Declared attributes: required ones are present (`attribute-missing`) and values match their type (`attribute-type-mismatch`).
- Declared relations: checked as in §11.
- Undeclared keys are allowed and not checked. Strict schemas may come later.

For example, this stays valid even though `some_personal_metadata` is not in the schema:

```yaml
type: transcript
title: Episode 42
created_at: 2026-10-06
some_personal_metadata: foo
```

### Scope of a run

- `knott validate` (no args) checks every schema and every entity.
- `knott validate PATH...` always checks every schema, because entity checks depend on them. Entity checks cover only the given files, or the entities under the given directories. Relation targets outside those paths are still read to check their type.
- An explicitly given file that is not an entity is an error (`not-an-entity`).

---

## 14. CLI

Keep the CLI deliberately small:

```
knott init [PATH]
knott validate [PATH...]
knott types
knott version
knott skill install [PATH]
knott view [PATH]
```

### `knott init [PATH]`

Creates `.knott/schemas/` and `.knott/config.yaml` in `PATH` (default: cwd). No content directories.

If `.knott/` already exists, it changes nothing, prints that the vault is already initialized, and exits with code `0`.

### `knott validate [PATH...]`

See §13 for scope and §20 for output.

### `knott types`

Prints discovered type names, one per line, sorted:

```
feedback
script
transcript
```

If schema errors exist, `types` still prints the types it could load, writes the errors to stderr, and exits with code `1`.

### `knott version`

Prints the installed Knott version.

### `knott view [PATH] [-o FILE] [--no-open]`

Writes the vault's ontology (types, attributes, relations, entity counts) as one self-contained static HTML page and opens it in the browser. No server and no network. Relations to undefined types point to a dashed "ghost" type. Schema errors still produce a page, with a note to run `knott validate`; a vault with no types exits with code `2`. See `docs/commands/view.md`.

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
- where schemas live and how to read them
- how to discover types (`knott types`)
- how to create an entity and write relations (relative paths, Markdown-link form, quoted)
- that `knott validate <file>` must be run after every change

Typical agent workflow:

1. Run `knott types` and look in `.knott/schemas/`.
2. Pick the relevant type and read its schema.
3. Create or update the Markdown entity.
4. Write relations as relative paths.
5. Run `knott validate <file>`.
6. Fix every reported issue before finishing.

The skill describes usage. The CLI provides deterministic behavior.

---

## 17. Indexing and search

Out of scope for v0. No SQLite, FTS, vector DBs, embeddings, graph DBs, RDF stores, persistent or background indexes.

Any future index must be derived, disposable, and fully rebuildable from the files:

```
Markdown files → rebuildable derived index → search / traversal / retrieval
```

---

## 18. Semantic model

Knott borrows vocabulary from RDF (entity, attribute, relation/predicate, schema) but does not implement RDF. Not in v0: RDF serialization, RDFS, OWL, SPARQL, reasoning, inference, inverse/symmetric/transitive properties, cardinality constraints beyond `required`.

The model must stay small enough to understand by reading a few YAML files.

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
schema-unknown-target      schema-field-conflict
entity-invalid-frontmatter entity-unknown-type        not-an-entity
attribute-missing          attribute-type-mismatch
relation-missing           relation-invalid-value     relation-target-outside-vault
relation-target-not-found  relation-target-not-entity relation-target-type-mismatch
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
types = vault.types()              # list[str], sorted
ontology = vault.ontology()        # Ontology: types with attributes, relations, counts
```

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
├── duplicate-schema-type/
└── schema-unknown-key/
```

At minimum, test: schema discovery and parsing, entity detection, attribute typing, relation parsing and resolution, target type checks, duplicate schema handling, the CLI output format, and exit codes.

---

## 23. Explicitly out of scope

Do not add, unless needed purely to meet the requirements above:

database as source of truth · search indexes · semantic or vector search · embeddings · stable entity IDs · automatic inverse relations · global relation registry · RDF / OWL · inference or reasoning · schema inheritance, composition, or versioning · migration framework · UI (an interactive or served app; the static page `knott view` writes is not one) · HTTP server · daemon · filesystem watcher · automatic knowledge extraction · automatic memory selection · agent deciding autonomously what to persist · plugin architecture · wikilink resolution.

Avoid speculative abstractions. Prefer the smallest implementation that satisfies the contract.

---

## 24. Definition of Done

Given `.knott/schemas/script.yaml`:

```yaml
type: script
attributes:
  title:
    type: string
    required: true
```

and `.knott/schemas/transcript.yaml`:

```yaml
type: transcript
relations:
  derived_from:
    target: script
    description: >
      The script from which this transcript was produced.
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
discover schemas → parse Markdown + frontmatter → validate attributes → resolve and validate relations
```

Do not build beyond it unless this spec requires it.

---

## 26. Proposed additions (not required for v0; accept or drop)

These are cheap and fit the agent-first goal, but they add scope:

- `knott validate --format json`: emits `{ok, stats, issues[]}` using the issue fields from §20. Agents should not have to parse text output.
- `knott types --verbose`: prints each type's `description` and schema path, so an agent can go straight to the right YAML.
- `knott skill`: prints the bundled `SKILL.md`, so agents installed through `uvx` can find it without the repo.
