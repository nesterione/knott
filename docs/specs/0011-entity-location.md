---
type: spec
title: "0011: Entity location"
status: implemented
created_on: 2026-11-25
released_in: "0.10.0"
realizes:
  - "[Entity location](../intents/entity-location.md)"
decisions:
  - "[0002](../decisions/0002-relative-paths-not-ids.md)"
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Entity](../concepts/entity.md)"
  - "[Vault](../concepts/vault.md)"
amends:
  - "[0005](0005-concept-files.md)"
---
# 0011: Entity location

## Summary

A concept can declare `path`: the folders its entities must be stored in. `knott validate` reports an entity that is somewhere else, and `knott types --verbose` shows the folders, so an agent knows where to create the file. A concept without `path` can live anywhere, as today. The change is additive.

## Behaviour

### The `path` key

```yaml
# .knott/concepts/episode.md
---
name: episode
path: episodes/*          # episodes/2026, episodes/2027, …
---
```

`path` is a top-level key of a concept file. Its value is one pattern, or a non-empty list of patterns.

- A pattern is matched against the **folder** of the entity: the vault-relative POSIX path of its directory. The file name is never part of the match; [0012](0012-entity-file-names.md) covers it.
- The entity is in the right place when its folder matches **at least one** pattern.
- A pattern is a `/`-separated list of segments, matched whole and with regard to case:

  | Pattern | Matches |
  |---|---|
  | `specs` | the folder `specs` only, not its subfolders |
  | `episodes/*` | any folder directly in `episodes`. `*` is any run of characters inside one segment, also none: `drafts-*` |
  | `episodes/**` | `episodes` and every folder below it. `**` is zero or more whole segments |
  | `**/specs` | a folder named `specs` at any depth |
  | `.` | the vault root |

- No other character is special: no `?`, `[…]`, `{a,b}` and no regular expressions. Alternatives are written as a list.
- A trailing `/` is ignored.
- A pattern that starts with `*` must be quoted (`path: "**/specs"`): YAML reads an unquoted leading `*` as an alias, and the file is then `schema-invalid-yaml`.

### Checks on `path`

Each of these is `schema-invalid-field` at the line of the pattern. The concept still loads, without `path`:

- a value that is not a string or a non-empty list of strings;
- an empty pattern, one that starts with `/`, contains `\` or an empty segment, or has a `.` or `..` segment (a lone `.` is the root);
- `**` that is not a whole segment (`a**`);
- the same pattern twice in the list.

An empty `path:` is the same as no key. A pattern that no existing folder matches is valid. The `field` of these issues is `path`.

## Issue codes

| Code | Stage | When | `field` / `line` |
|---|---|---|---|
| `entity-misplaced` | entity | the entity's type declares `path` and the entity's folder matches none of the patterns | none / the line of `type` |

```
✗ notes/episode-42.md:2
  `episode` entities are stored in `episodes/*`, but this file is in `notes`
```

Several patterns are joined with `or`. The vault root is printed as `.`.

## CLI and API

- `knott validate`: reports `entity-misplaced` like any other error. The other checks on the entity still run.
- `knott types --verbose`: a line `path: episodes/*` after `template:`; several patterns are joined with ` | `. No line when the concept has no `path`.
- `knott view`: the type's panel shows the patterns.
- Python API: `OntologyType.entity_paths: list[str]`, `[]` when not declared. (`OntologyType.path` is already the concept file.)
- Agent skill: before creating an entity, read `path` and put the file in a folder that matches.

## Edge cases

| Case | Result |
|---|---|
| `path: specs`, entity at `specs/old/0001.md` | `entity-misplaced`; write `specs/**` to allow subfolders |
| `path: episodes/*`, entity at `episodes/42.md` | `entity-misplaced`: `*` needs one segment |
| `path: **/specs`, unquoted | `schema-invalid-yaml`; write `"**/specs"` |
| `knott validate SPECS/a.md`, the folder on disk is `specs` | `entity-misplaced`: a path argument is taken as written; pass it as it is on disk |
| `path: Specs`, entity in `specs/` | `entity-misplaced`, also on a file system that ignores case |
| A file in `specs/` with another type, or with no `type` | not checked: `path` says where a type lives, not what a folder holds |

## Out of scope

- Regular expressions in `path`. A glob covers folders, and `[0-9]{4}` style rules belong to file names ([0012](0012-entity-file-names.md)).
- Moving a misplaced file. References are relative paths ([0002](../decisions/0002-relative-paths-not-ids.md)), so a move must rewrite links in other files; a later spec.
- A folder that may hold only one type.
- Leaving folders out of the vault: [issue #19](https://github.com/nesterione/knott/issues/19).
- Reporting the issue as a warning while a vault is being migrated: [issue #22](https://github.com/nesterione/knott/issues/22).

## Compatibility

Additive. A concept with a `path` key got `schema-invalid-field` before. Adding `path` to a concept makes entities stored elsewhere invalid; `knott validate` lists them. Ontology API addition only. Version 0.10.0.
