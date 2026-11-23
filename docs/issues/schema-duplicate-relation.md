---
type: issue_code
code: schema-duplicate-relation
stage: schema
about: "[Relation](../concepts/relation.md)"
---
# `schema-duplicate-relation`

Two relation files in `.knott/relations/` have the same `name`. The message names both files.

## Example

```
✗ .knott/relations/supersedes.md:2  name
  relation `supersedes` is defined twice: in `.knott/relations/old/supersedes.md` and in `.knott/relations/supersedes.md`
  each relation must be defined by exactly one relation file
```

## Fix

Delete one, or change its `name`. A relation's identity is the `name` value, not the filename.

## Notes

The first file by sorted path wins and stays loaded; the issue is reported on the later one. Relation names and concept names are separate, so a relation and a type may share a name.
