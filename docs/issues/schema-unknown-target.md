---
type: issue_code
code: schema-unknown-target
stage: schema
about: "[Relation](../concepts/relation.md)"
---
# `schema-unknown-target`

A relation's `target` names a type no schema defines.

## Example

```yaml
relations:
  about:
    target: episode   # no episode.yaml
```

## Fix

Create the target schema, or fix the spelling. The message lists the known types.

## Notes

Validation ignores the broken relation, so entity values for it are not checked until fixed. [`knott view`](../commands/view.md) still draws it, as an arrow to a dashed ghost box.
