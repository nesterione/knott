---
type: issue_code
code: schema-invalid-field
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-invalid-field`

A concept-file key is unknown, missing, or has the wrong shape: a typo like `propertes:`, a missing `name`, a name that doesn't match `^[a-z][a-z0-9_-]*$`, an unknown property type like `float`, `required: yes`, a definition that isn't a mapping, or a reference with no `target` or an empty one.

It also reports the parts of the old format and the reserved names:

| Found | Message says |
|---|---|
| `type:` at the top | concept files use `name:`; `type:` belongs to entities |
| `attributes:` or `relations:` | merged into `properties`; run `knott migrate` |
| a top-level property named `type` or `kid` | reserved for knott |
| `relation:` on a reference | reserved for relation definitions, not supported yet |
| a `.knott/relations/` folder | reserved for relation definitions, not supported yet |

## Example

```yaml
---
name: transcript
propertes:
  title:
    type: string
---
```

## Fix

Use only the keys in the [schema](../concepts/schema.md) table. Property types are `string`, `integer`, `number`, `boolean`, `date`, `datetime`, `list`, `object`, `map` and `reference`. `required` takes `true` or `false`. For a file in the old format, run [`knott migrate`](../commands/migrate.md).

## Notes

As long as `name` itself is valid, the type is still registered, so one typo doesn't turn every entity into `entity-unknown-type`. A property definition that is unusable (unknown or missing `type`, missing `target`, not a mapping) is skipped. An invalid `required` or `description` falls back to its default (`false` / none), and the field stays active.
