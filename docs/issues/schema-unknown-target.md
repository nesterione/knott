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

The broken relation is dropped, so entity values for it are not checked until fixed.
