---
type: issue_code
code: relation-target-type-mismatch
stage: relation
about: "[Reference resolution](../concepts/reference-resolution.md)"
---
# `relation-target-type-mismatch`

The target is an entity, but its `type` isn't the property's `target` or a [subtype](../concepts/schema.md#inheritance) of it, or of any of them when `target` is a list. The message lists every allowed type. An [open reference](../concepts/relation.md#open-references) (`target: any`) never reports it.

## Example

```yaml
# concept transcript: derived_from → script, recording_of → [episode, meeting]
derived_from: ../scripts/foo.md        # but foo.md has type: feedback
recording_of: ../people/ann.md         # expects target type `episode` or `meeting`
```

## Fix

Point at an entity of the expected type, or fix the target's `type`. If the property should accept this type, add it to `target` in the concept file.
