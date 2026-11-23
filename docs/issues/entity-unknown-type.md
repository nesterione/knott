---
type: issue_code
code: entity-unknown-type
stage: entity
about: "[Entity](../concepts/entity.md)"
---
# `entity-unknown-type`

An entity's `type` isn't the `name` of any concept file (including `type:` left empty or set to a non-string).

## Example

```yaml
type: podcast   # no concept file has name: podcast
```

## Fix

Fix the spelling, or add `.knott/concepts/podcast.md` with `name: podcast`. The message lists the known types.

## Notes

Run `knott types` to see what exists.
