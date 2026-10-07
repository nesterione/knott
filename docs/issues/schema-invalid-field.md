---
type: issue_code
code: schema-invalid-field
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-invalid-field`

A schema key is unknown, missing, or has the wrong shape: a typo like `atributes:`, a missing `type`, a type name that doesn't match `^[a-z][a-z0-9_-]*$`, an unknown attribute type like `float`, `required: yes`, or a definition that isn't a mapping.

## Example

```yaml
atributes:
  title:
    type: string
```

## Fix

Use only the keys in the schema table. Attribute types are `string`, `integer`, `number`, `boolean`, `date`, `datetime`. `required` takes `true` or `false`.

## Notes

As long as `type` itself is valid, the type is still registered, so one typo doesn't turn every entity into `entity-unknown-type`. A field definition that is unusable (unknown or missing attribute `type`, missing relation `target`, not a mapping) is skipped. An invalid `required` or `description` falls back to its default (`false` / none), and the field stays active.
