---
type: issue_code
code: schema-extends-cycle
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-extends-cycle`

A chain of `extends` leads back to where it started, so a concept would be its own ancestor. A concept that extends itself is the shortest case.

## Example

```yaml
# .knott/concepts/a.md
name: a
extends: b
---
# .knott/concepts/b.md
name: b
extends: a
```

## Fix

Remove one `extends` in the cycle the message shows (`` `a` → `b` → `a` ``).

## Notes

One issue per concept in the cycle, at the line of its `extends`. Each of them loads without a parent. A concept below the cycle keeps its chain up to the first concept in it.
