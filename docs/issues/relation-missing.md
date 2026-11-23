---
type: issue_code
code: relation-missing
stage: relation
about: "[Relation](../concepts/relation.md)"
---
# `relation-missing`

A `required: true` reference is absent, `null` or `""`. For a required `list` of references, `[]` counts as absent too. Nested references are reported with their full path, e.g. `speakers[0].person`.

## Example

```yaml
# concept: sources is a required list of references
sources: []
```

## Fix

Add a reference, or at least one item for a list.
