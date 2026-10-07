---
type: issue_code
code: schema-field-conflict
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-field-conflict`

A field is named `type` (reserved for the entity type), or the same name appears under both `attributes` and `relations`.

## Example

```yaml
attributes:
  source:
    type: string
relations:
  source:
    target: script
```

## Fix

Rename one of the fields.
