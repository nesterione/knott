---
type: issue_code
code: loop-invalid-target
stage: schema
about: "[Loop](../concepts/loop.md)"
---
# `loop-invalid-target`

A [loop](../concepts/loop.md) file names something that doesn't exist or doesn't fit: its `type` is not a concept, its `property` is not a top-level `enum` of that type, a stage is not an option of the enum, or a need names an unknown property, inverse or type.

## Example

```yaml
# concept episode: status: { type: enum, options: [idea, recorded, published] }
name: episode-production
type: episode
property: status
stages:
  idea:
  publshed:                              # not an option; did you mean `published`?
  recorded: { needs: [recorded] }        # no such property; did you mean `recorded_at`?
```

## Fix

Use the names the concept and relation files define. `knott types --verbose` lists each type's properties and options, and each relation's `inverse`.

## Notes

The loop is not loaded until this is fixed, so its entities are not checked and it is missing from `knott loops` and `knott view`. For `<inverse>: <type>`, the type must have a reference that names the relation and can target the loop's type. A need can't be the loop's own stage property.
