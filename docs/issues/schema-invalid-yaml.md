---
type: issue_code
code: schema-invalid-yaml
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-invalid-yaml`

A schema file can't be parsed: invalid YAML, an empty file, or YAML that isn't a mapping.

## Example

```yaml
type: [oops
```

## Fix

Fix the YAML syntax. A schema file must be a mapping with at least `type:`.

## Notes

The type it would have defined is not registered, so entities of that type also report `entity-unknown-type`.
