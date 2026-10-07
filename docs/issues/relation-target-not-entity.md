---
type: issue_code
code: relation-target-not-entity
stage: relation
about: "[Reference resolution](../concepts/reference-resolution.md)"
---
# `relation-target-not-entity`

The target file exists but isn't an entity: no frontmatter, no `type`, or invalid frontmatter.

## Example

```yaml
derived_from: ../notes/plain.md   # no frontmatter
```

## Fix

Point at an entity, or give the target frontmatter with the right `type`.
