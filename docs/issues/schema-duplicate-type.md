---
type: issue_code
code: schema-duplicate-type
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-duplicate-type`

Two concept files have the same `name`. The message names both files.

## Example

```yaml
# .knott/concepts/script.md and .knott/concepts/legacy/script.md
---
name: script
---
```

## Fix

Delete one, or change its `name`. The type's identity is the `name` value, not the filename.

## Notes

The first file by sorted path wins and stays loaded; the issue is reported on the later one.
