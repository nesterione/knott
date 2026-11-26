---
type: issue_code
code: schema-unknown-target
stage: schema
about: "[Relation](../concepts/relation.md)"
---
# `schema-unknown-target`

A reference's `target` names a type no concept file defines. With a list of targets, each unknown name is its own issue. `field` is the full key path, e.g. `properties.sources.items.target`.

## Example

```yaml
properties:
  about:
    type: reference
    target: [episode, podcast]   # no concept file has name: podcast
```

## Fix

Create the concept file, or fix the spelling. For a reference to any entity, write `target: any`, lowercase and alone (`Any` and `"*"` are unknown names). The message lists the known types.

## Notes

The unknown name is dropped and the known ones are still enforced: above, an `about` value must point at an `episode`. If no target is left, values are still checked for shape and resolved, but any entity type passes. [`knott types --verbose`](../commands/types.md) shows the name as `podcast (unknown)`, and [`knott view`](../commands/view.md) draws no arrow for it.
