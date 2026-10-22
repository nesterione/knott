---
type: issue_code
code: relation-target-ambiguous
stage: relation
about: "[Reference resolution](../concepts/reference-resolution.md)"
---
# `relation-target-ambiguous`

A `kid:` reference names a `kid` that more than one entity claims, so knott can't tell which one is meant.

## Example

```yaml
includes:
  - kid:3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21   # claimed by draugas.md and draugas-copy.md
```

## Fix

Fix the [`kid-duplicate`](kid-duplicate.md) first: give the copied file a new `kid`. The reference then resolves to the original.
