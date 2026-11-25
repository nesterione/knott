---
type: command
title: knott validate
synopsis: knott validate [PATH...] [--format text|json] [--fix]
writes_files: true
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Entity](../concepts/entity.md)"
  - "[Issue](../concepts/issue.md)"
---
# knott validate

The primary command. It loads every [concept file](../concepts/schema.md) in `.knott/concepts/` every [relation definition](../concepts/relation.md#relation-definitions) in `.knott/relations/` every [connector](../concepts/file.md#uris-and-connectors) in `.knott/connectors/` and every [loop](../concepts/loop.md) in `.knott/loops/`, then validates entities. An entity at a stage of a loop must meet what that stage needs ([`loop-stage-unmet`](../issues/loop-stage-unmet.md)). A vault that still has `.knott/schemas/` reports only [`schema-legacy-layout`](../issues/schema-legacy-layout.md); run [`knott migrate`](migrate.md).

| Invocation | Schemas checked | Entities checked |
|---|---|---|
| `knott validate` | all | all |
| `knott validate a.md notes/` | all (entity checks depend on them) | only `a.md` and entities under `notes/` |

Relation targets outside the given paths are still read to check their type. A loop of an `acyclic` relation ([`relation-cycle`](../issues/relation-cycle.md)) is reported when any entity on it is in scope. [File](../concepts/file.md) values are resolved only for the entities in scope. A given file that isn't an entity is reported as `not-an-entity`.

## Output

Success:

```
✓ 2 schemas
✓ 2 entities
✓ 1 relation
✓ vault is valid
```

"Schemas" counts the types loaded from concept files. "Relations" counts each resolved reference at any depth, so a list of three counts as 3. File values are checked but not counted. On failure, each issue is printed, then `N validation errors`.

`--format json` prints `{"ok": …, "stats": {…}, "issues": [{code, path, line, field, message}]}`, the form agents should parse.

## `--fix`

Gives a [kid](../concepts/kid.md) to every checked entity that has no `kid` key, then validates. Each changed file is listed first:

```
$ knott validate --fix lexemes/
+ kid  lexemes/namas.md

✓ 2 schemas
…
```

The edit is a single inserted line, `kid: <new uuid>`, after the `type:` line; nothing else in the file changes. `--fix` never touches an existing `kid`, even an empty, invalid or duplicated one. With `--format json`, the output gains `"fixed": [{"path", "kid"}]`. Without `--fix`, `validate` never writes.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | valid |
| `1` | one or more validation issues |
| `2` | usage error: no vault, missing path, path outside the vault, malformed `.knott/config.yaml` |
