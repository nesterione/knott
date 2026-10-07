---
type: issue_code
code: not-an-entity
stage: entity
about: "[Entity](../concepts/entity.md)"
---
# `not-an-entity`

A file passed explicitly to `knott validate PATH` is not an entity: no frontmatter, no `type`, or not a `.md` file.

## Example

```yaml
knott validate notes/plain-note.md
```

## Fix

Add frontmatter with a `type`, or don't pass the file. Directories passed as PATH silently skip ordinary notes; only explicit files get this error.
