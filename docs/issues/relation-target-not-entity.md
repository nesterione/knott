---
type: issue_code
code: relation-target-not-entity
stage: relation
about: "[Reference resolution](../concepts/reference-resolution.md)"
---
# `relation-target-not-entity`

The target file exists but isn't an entity: no frontmatter, no `type`, invalid frontmatter, or a place outside the [included folders](../concepts/vault.md#included-folders). The message says which.

## Example

```yaml
derived_from: ../notes/plain.md   # no frontmatter
```

## Fix

Point at an entity, or give the target frontmatter with the right `type`. For a file outside the included folders, add its folder to `include` in `.knott/config.yaml`, or move the file into an included folder.
