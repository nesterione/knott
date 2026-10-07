---
type: command
title: knott validate
synopsis: knott validate [PATH...] [--format text|json]
writes_files: false
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Entity](../concepts/entity.md)"
  - "[Issue](../concepts/issue.md)"
---
# knott validate

The primary command. It loads all schemas, then validates entities.

| Invocation | Schemas checked | Entities checked |
|---|---|---|
| `knott validate` | all | all |
| `knott validate a.md notes/` | all (entity checks depend on them) | only `a.md` and entities under `notes/` |

Relation targets outside the given paths are still read to check their type. A given file that isn't an entity is reported as `not-an-entity`.

## Output

Success:

```
✓ 2 schemas
✓ 2 entities
✓ 1 relation
✓ vault is valid
```

"Relations" counts each resolved reference, so a list of three counts as 3. On failure, each issue is printed, then `N validation errors`.

`--format json` prints `{"ok": …, "stats": {…}, "issues": [{code, path, line, field, message}]}`, the form agents should parse.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | valid |
| `1` | one or more validation issues |
| `2` | usage error: no vault, missing path, path outside the vault, malformed `.knott/config.yaml` |
