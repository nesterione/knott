---
type: issue_code
code: schema-invalid-yaml
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-invalid-yaml`

A concept file can't be parsed: it has no frontmatter, the frontmatter is invalid YAML or never closes, or it isn't a mapping.

## Example

```yaml
---
name: [oops
---
```

## Fix

Fix the YAML syntax. A concept file starts with a `---` line, then at least `name: <type>`, then a closing `---` line.

## Notes

The type it would have defined is not registered, so entities of that type also report `entity-unknown-type`.
