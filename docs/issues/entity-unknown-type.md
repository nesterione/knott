---
type: issue_code
code: entity-unknown-type
stage: entity
about: "[Entity](../concepts/entity.md)"
---
# `entity-unknown-type`

An entity's `type` doesn't name any discovered schema (including `type:` left empty or set to a non-string).

## Example

```yaml
type: podcast   # no schema defines podcast
```

## Fix

Fix the spelling, or add `.knott/schemas/podcast.yaml`. The message lists the known types.

## Notes

Run `knott types` to see what exists.
