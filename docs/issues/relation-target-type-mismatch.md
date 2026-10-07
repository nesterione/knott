---
type: issue_code
code: relation-target-type-mismatch
stage: relation
about: "[Reference resolution](../concepts/reference-resolution.md)"
---
# `relation-target-type-mismatch`

The target is an entity, but its `type` isn't the relation's `target`.

## Example

```yaml
# transcript.yaml: derived_from → script
derived_from: ../scripts/foo.md   # but foo.md has type: feedback
```

## Fix

Point at an entity of the expected type, or fix the target's `type`. If the relation should accept this type, change the schema.
