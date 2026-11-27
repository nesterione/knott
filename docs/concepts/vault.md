---
type: concept
title: Vault
summary: An ordinary directory containing `.knott/`; everything under it is the knowledge base.
spec_section: "§3"
related:
  - "[Entity](entity.md)"
  - "[Schema](schema.md)"
---
# Vault

A vault is any directory with a `.knott/` subdirectory:

```
my-vault/
├── .knott/
│   ├── config.yaml        # knott_version, written once by `knott init`; optional `include`
│   ├── concepts/          # one Markdown concept file per entity type
│   ├── relations/         # optional: one Markdown file per relation definition
│   ├── connectors/        # optional: one Markdown file per store of files kept elsewhere
│   └── loops/             # optional: one Markdown file per loop
└── … your Markdown, organized however you like
```

## Finding the root

Knott starts at the current directory (or the path you pass) and walks **up** until it finds a directory containing `.knott/`. So `knott validate` works from any subfolder. No vault found → exit code `2`.

## What gets scanned

Every `*.md` file under the included folders (the whole vault, unless you set [`include`](#included-folders)), recursively, except:

- directories whose name starts with `.` (`.git`, `.knott`, `.obsidian`, …)
- symlinked directories (never followed)

A [file property](file.md) can point at any file in the vault, in hidden folders too.

`.gitignore` is not consulted. Files are sorted, so output is deterministic.

## Config

`.knott/config.yaml` is optional. If present it must be empty or a YAML mapping; a malformed file is a configuration error (exit `2`). Only `knott init` writes it, and it writes only `knott_version`.

## Included folders

A vault is often the root of a repository that also holds code, fixtures or vendored files. Name the folders that hold knowledge, by hand, in `.knott/config.yaml`:

```yaml
knott_version: 0.1.0
include:
  - docs
  - notes/projects
```

- `include` is one folder or a list of them: vault-relative paths, exact case. `.` is the vault root. Without the key the whole vault is scanned.
- **A Markdown file that is not inside the included folders is never an entity.** No command reads it, counts it, lists it, gives it a `kid` or rewrites it.
- A file directly in the vault root is inside them only when `.` is listed.
- Folders are literal: no patterns, no way to exclude a subfolder, no hidden folders.

What you see when a file is outside them:

| You do | You get |
|---|---|
| reference it by path from an entity | [`relation-target-not-entity`](../issues/relation-target-not-entity.md); the file is not read |
| reference its `kid` | [`relation-target-not-found`](../issues/relation-target-not-found.md); the `kid` is never a duplicate |
| `knott validate notes/plan.md` | [`not-an-entity`](../issues/not-an-entity.md) |
| `knott validate notes/` | nothing checked, exit `0` |
| `knott refs`, `knott show`, `knott mv` on it, or `knott mv` to a place outside | exit `2` |
| point a [file property](file.md) at it | accepted: a file is a value, not an entity |

Each message names the setting:

```
✗ notes/plan.md
  not a Knott entity: it is outside the included folders (`docs`); add its folder to `include` in .knott/config.yaml
```

`.knott/` is always loaded, and the vault root is found as before. A folder that does not exist (with that exact case), is not a folder, is hidden, is a symbolic link, or is written with `*`, `..` or a leading `/` is a configuration error: every command prints one line and exits `2`, so a mistyped folder cannot make an empty vault look valid.

```
$ knott validate
error: invalid `include` in .knott/config.yaml:4: folder `doc` does not exist
```
