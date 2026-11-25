---
type: issue_code
code: relation-symmetric-mismatch
stage: schema
about: "[Relation](../concepts/relation.md)"
---
# `relation-symmetric-mismatch`

A symmetric relation reads the same both ways, so some combinations don't fit it:

| Found | Reported at |
|---|---|
| `symmetric: true` with an `inverse` | the relation file's `inverse:` line |
| `symmetric: true` with `acyclic: true` (every symmetric link is a two-step cycle) | the relation file's `acyclic:` line |
| a property names a symmetric relation, but its targets don't include the property's own concept | the concept file's `relation:` line |

## Example

```yaml
# .knott/concepts/decision.md; `related` is symmetric
properties:
  see_also:
    type: list
    items: { type: reference, relation: related, target: concept }
```

```
✗ .knott/concepts/decision.md:7  properties.see_also.items.relation
  `properties.see_also.items.relation` names symmetric relation `related`, but its targets (`concept`) don't include its own concept `decision`
  a symmetric link must be able to point back; add `decision` to `target` or name another relation
```

## Fix

In the relation file, remove `inverse` or `acyclic`, or remove `symmetric`. On the property, add its own concept to `target`, or name a relation that isn't symmetric.

## Notes

Only known targets count. A property whose targets are `[concept, guide]`, on `concept`, is valid. A symmetric relation that is also `acyclic` is not checked for cycles.
