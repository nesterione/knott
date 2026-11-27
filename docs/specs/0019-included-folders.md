---
type: spec
title: "0019: Included folders"
status: implemented
created_on: 2026-11-26
released_in: "0.15.0"
realizes:
  - "[Included folders](../intents/included-folders.md)"
decisions:
  - "[0006](../decisions/0006-symlinks-and-containment.md)"
concepts:
  - "[Vault](../concepts/vault.md)"
  - "[Entity](../concepts/entity.md)"
amends:
  - "[0004](0004-kid-identity.md)"
  - "[0006](0006-relation-definitions.md)"
  - "[0016](0016-list-and-show-entities.md)"
  - "[0018](0018-move-entities.md)"
---
# 0019: Included folders

## Summary

`.knott/config.yaml` gains one key, `include`: the folders knott reads Markdown from. Without it knott reads the whole vault, as today. With it, a Markdown file outside the listed folders is never an entity and no command reads it, so vendored files, fixtures and build output next to the knowledge base are neither read nor reported. Nothing breaks for a vault that does not set the key.

## Behaviour

### The `include` key

```yaml
# .knott/config.yaml
knott_version: 0.1.0
include:
  - docs
  - notes/projects
```

- `include` is a top-level key of `.knott/config.yaml`. Its value is one folder, or a non-empty list of folders.
- A missing key, or `include: .`, is the vault root: every folder is scanned, as today.
- A folder is a vault-relative POSIX path, matched with regard to case. `.` is the vault root. A trailing `/` is ignored.
- Folders are literal. There are no patterns: `*` in an entry is refused, so that patterns can be added later without changing the meaning of a vault.
- The key is edited by hand. `knott init` does not write it, and no command changes it.

### Inside the included folders, and the scanned set

Two terms, kept apart on purpose:

- A file is **inside the included folders** when it is below at least one of them, at any depth. This is a test on the path alone.
- The **scanned set** is what discovery finds: every `*.md` file inside the included folders that today's rules reach. Those rules are unchanged:
  - a folder whose name starts with `.` is skipped;
  - a symlinked folder is not followed;
  - `.gitignore` is not consulted;
  - paths are sorted, and a file below two included folders (`docs` and `docs/specs`) is in the set once.

With no `include` key every file of the vault is inside the included folders, and the scanned set is exactly what knott discovers today.

A `*.md` file directly in the vault root is inside the included folders only when `.` is one of them. There is no way to scan the root without its subfolders.

### One rule for every command

**A Markdown file that is not inside the included folders is never an entity**, whatever its frontmatter says. Knott does not read it, count it, list it, give it a `kid` or rewrite it.

Every command that enumerates Markdown uses the scanned set:

| Where | Effect |
|---|---|
| `knott validate` | Checks the entities of the scanned set. The `entities` and `relations` counts cover only them. |
| `knott validate DIR` | Checks the entities of the scanned set below `DIR`. A `DIR` with none is not an error, as a folder of plain notes today. |
| `knott validate --fix` | Gives a `kid` only to entities of the scanned set. |
| `kid:` references, `kid-duplicate` | The kid index holds the scanned set. A `kid` carried only by a file outside it is `relation-target-not-found`, and is never a duplicate. |
| `relation-cycle`, reverse lookup, `knott refs` | Built from the references of the scanned set. |
| `knott types`, `knott view`, `Knott.ontology()` | Entity counts cover the scanned set. |
| `knott loops`, `loop-stage-unmet` | Only entities of the scanned set are on a board. |
| `knott migrate` | Reads entity frontmatter from the scanned set only. |
| `knott list`, `Knott.entities()` ([0016](0016-list-and-show-entities.md)) | List only the scanned set. |
| `knott mv` ([0018](0018-move-entities.md)) | Searches the scanned set for links, plus the `.knott/` files 0018 names. A link in a file outside the included folders is not rewritten. |

Where a single file is named, the test is the path:

| Where | A file not inside the included folders |
|---|---|
| The target of a path reference | `relation-target-not-entity`. The file is not read. A target that does not exist is `relation-target-not-found`, as today. |
| `knott validate FILE` | `not-an-entity`. |
| `knott refs PATH`, `knott show PATH`, `Knott.show()` | Exit `2` (`KnottError`): not an entity. A folder gets the message it gets today, whether it is an included folder or not. The same for an entity path given as the value of a reference filter (`knott list --where`, `Knott.entities(where=…)`). |
| An outgoing reference in `knott show` | Listed with the error `relation-target-not-entity`, its target's path, and no type or `kid`. |
| `knott mv SOURCE DEST` | Exit `2` when `SOURCE` is not inside the included folders, and when `DEST` is not: the file would stop being an entity and every reference to it would break. |

A file in a hidden folder that *is* inside the included folders (`docs/.drafts/a.md` with `include: [docs]`) is treated exactly as today, in every row above. This spec does not change what knott does with hidden folders.

Not affected:

- **Finding the vault root.** It is still the nearest folder with `.knott/`.
- **`.knott/` itself.** Concept, relation, connector and loop files are always loaded.
- **File properties.** A `file` value may point at any file in the vault, inside the included folders or not. A file is a value, not an entity.
- **Concept `path` and `filename`** ([0011](0011-entity-location.md), [0012](0012-entity-file-names.md)). They are checked for the entities knott sees. A `path` pattern that matches only folders outside the included folders is not an error.

### Messages

Each message says why and names the setting. The included folders are listed in the order written, joined with `, `.

`relation-target-not-entity` keeps its wording and gets a new reason:

```
✗ docs/specs/0019-included-folders.md:6  realizes[0]
  relation `realizes[0]` points to `../../notes/plan.md`, which is not a Knott entity: it is outside the included folders (`docs`); add its folder to `include` in .knott/config.yaml
```

`not-an-entity`, for `knott validate notes/plan.md`:

```
✗ notes/plan.md
  not a Knott entity: it is outside the included folders (`docs`); add its folder to `include` in .knott/config.yaml
```

`knott refs` and `knott show`:

```
error: not a Knott entity: notes/plan.md; it is outside the included folders (`docs`); add its folder to `include` in .knott/config.yaml
```

`knott mv` moves plain notes too, so it keeps the wording of [0018](0018-move-entities.md) for `SOURCE`, and says what would happen for `DEST`:

```
error: not a Markdown file knott sees: notes/plan.md; it is outside the included folders (`docs`); add its folder to `include` in .knott/config.yaml
error: cannot move to notes/a.md: the file would stop being an entity and every reference to it would break; it is outside the included folders (`docs`); add its folder to `include` in .knott/config.yaml
```

### Checks on `include`

Each of these is a configuration error. Every command that opens a vault prints one line to stderr and exits `2`, as for a malformed `config.yaml` today; nothing is read or written.

- a value that is not a string or a non-empty list of strings (`include: []`, `include:` with no value, a number, a mapping);
- an empty entry, one that starts with `/`, contains `\`, `*` or an empty segment, or has a `.` or `..` segment (a lone `.` is the root);
- an entry with a segment that starts with `.` (`.github`, `docs/.drafts`): hidden folders are never scanned;
- an entry that does not exist with that exact case, or is not a folder;
- an entry that is a symbolic link, or is reached through one.

```
$ knott validate
error: invalid `include` in .knott/config.yaml:4: folder `doc` does not exist
```

The line is that of the entry. A folder that does not exist is an error and not an empty result, so that a mistyped entry cannot make an empty vault look valid.

## CLI and API

No new command or flag, and no new issue code. The output of every command keeps its form.

Python API:

- `Knott.included_folders`: a tuple of vault-relative POSIX paths, in the order written, duplicates removed, without trailing `/`. `(".",)` when the key is missing.
- `Knott.open()` raises `ConfigError` for the cases above, as it does for a malformed `config.yaml`.

`knott init` writes no `include` key.

## Edge cases

| Case | Result |
|---|---|
| No `config.yaml`, or one without `include` | The whole vault is scanned. |
| `include: docs` (a string) | The same as `include: [docs]`. |
| `include: [docs, docs/specs]` | The same as `include: [docs]`. |
| `include: [., docs]` | The same as `include: .`. |
| `include: [docs, docs]` | Allowed; `Knott.included_folders` is `("docs",)`. |
| `include: [docs/]` | The same as `include: [docs]`. |
| `include: ./` | The same as `include: .`. |
| `include: []`, or `include:` with no value | Configuration error: write `.` or remove the key. |
| `include: [doc]`, and only `docs/` exists | Configuration error. |
| `include: [Docs]`, the folder is `docs`, on a file system that ignores case | Configuration error: exact case, as for reference targets. |
| `include: [README.md]` | Configuration error: not a folder. |
| `include: [.github]` | Configuration error: hidden folder. |
| `include: [vendor]`, and `vendor` is a symbolic link to a folder | Configuration error. |
| `include: ["docs/*"]` | Configuration error: no patterns. |
| `include: [docs]`, and `docs/.drafts/a.md` exists | Not in the scanned set: hidden folders are skipped inside an included folder too. |
| `include: [docs]`, and `docs/a.md` references `.drafts/a.md` | As today: the target is inside the included folders, so it is read and judged by its frontmatter. |
| `include: [docs]`, `knott validate docs/.drafts/a.md` | As today: the file is read and validated. |
| `include: [docs]`, and `docs/a.md` references `../tests/.x/a.md` | `relation-target-not-entity`: not inside the included folders. |
| `include: [docs]`, and `docs/a.md` references `../README.md`, which exists | `relation-target-not-entity`, with the message above. |
| `include: [docs]`, and `docs/a.md` references `../missing.md` | `relation-target-not-found`, as today. |
| `include: [docs]`, and `docs/a.md` has a `file` property pointing at `../assets/logo.png` | Accepted, as today. |
| `include: [docs]`, and two entities, `docs/a.md` and `tests/b.md`, carry one `kid` | No `kid-duplicate`; `kid:` references resolve to `docs/a.md`. |
| `include: [docs]`, `knott validate .` | Checks the entities under `docs/`. |
| `include: [docs]`, `knott validate src/` | Checks nothing; exit `0` when the schemas are valid. |
| `include: [docs]`, `knott validate tests/b.md` | `not-an-entity`, exit `1`. |
| `include: [docs]`, `knott validate --fix` | `tests/b.md` is not changed. |
| `include: [docs]`, a concept declares `path: notes` | No issue; no entity can be in `notes/` while it is not included. |
| `include: [docs]`, `knott mv docs/a.md notes/a.md` | Exit `2`: `DEST` is not inside the included folders. |
| An included folder exists and holds no Markdown | Allowed. |
| The vault root is inside a larger repository, `include: [../shared]` | Configuration error: `..` segment. A vault never reads outside its root. |

## Out of scope

- Excluding folders (`ignore:`), patterns in `include`, and reading `.gitignore`. A later spec can add them on top of the list.
- Including a hidden folder, or the files of the root without its subfolders.
- Following a symlinked folder ([0006](../decisions/0006-symlinks-and-containment.md)).
- A flag on `knott init` that writes the key, and a command-line option that overrides it for one run.
- Changing what knott does with a file in a hidden folder. Inside the included folders it stays as it is.
- A warning for a `path` pattern that no included folder can satisfy.

## Compatibility

Additive. A vault without `include` behaves exactly as before. [0016](0016-list-and-show-entities.md) and [0018](0018-move-entities.md), released in 0.14.0, describe what they see as "outside `.knott/` and other hidden folders"; with `include` set, the rules above apply on top of that. A knott older than this change ignores the key and scans the whole vault, since unknown keys in `config.yaml` have always been accepted. Version 0.15.0.
