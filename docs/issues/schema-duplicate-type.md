---
type: issue_code
code: schema-duplicate-type
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-duplicate-type`

Two schema files define the same `type`. The message names both files.

## Example

```yaml
# .knott/schemas/script.yaml and .knott/schemas/legacy/script.yaml
type: script
```

## Fix

Delete or rename one. The type's identity is the `type` value, not the filename.

## Notes

The first file by sorted path wins and stays loaded; the issue is reported on the later one.
