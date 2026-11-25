---
type: issue_code
code: schema-duplicate-loop
stage: schema
about: "[Loop](../concepts/loop.md)"
---
# `schema-duplicate-loop`

Two [loop](../concepts/loop.md) files have the same `name`, or follow the same property of the same type, or of a type and its [subtype](../concepts/schema.md#inheritance): a loop on a type already follows its subtypes.

## Example

```yaml
# .knott/loops/a.md
name: episode-production
type: episode
property: status

# .knott/loops/b.md
name: episode-review
type: episode
property: status          # `episode.status` is already the stage of `episode-production`
```

## Fix

Give each loop its own name, and merge two loops that follow one property into one. A type can have several loops when each follows a different enum property.

## Notes

Reported at the second file in path order, which defines no loop.
