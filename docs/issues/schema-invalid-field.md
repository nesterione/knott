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
| `relation:` on a `list` or `map` | put `relation:` on `items` (or `values`) |
| `relation:` on any other non-reference shape | only allowed when `type` is reference |

It covers [relation files](../concepts/relation.md) in `.knott/relations/` too: an unknown key (with a "did you mean" suggestion), a missing or malformed `name` or `inverse`, `symmetric` or `acyclic` that isn't `true` or `false`, and `transitive`, which is reserved and not supported yet.

## Example

```yaml
---
name: transcript
propertes:
  title:
    type: string
---
```

```yaml
# .knott/relations/supersedes.md
---
name: supersedes
inverse: superseded_by
acyclic: yes
transitive: true
inverce: x
---
```

```
✗ .knott/relations/supersedes.md:4  acyclic
  `acyclic` must be true or false, got boolean `yes`

✗ .knott/relations/supersedes.md:5  transitive
  `transitive` is reserved, not supported yet; remove it

✗ .knott/relations/supersedes.md:6  inverce
  unknown key `inverce` in relation file; allowed keys: name, description, inverse, symmetric, acyclic; did you mean `inverse`?
```

## Fix

Use only the keys in the [schema](../concepts/schema.md) table, or, in a relation file, `name`, `description`, `inverse`, `symmetric` and `acyclic`. Property types are `string`, `integer`, `number`, `boolean`, `date`, `datetime`, `list`, `object`, `map` and `reference`. `required` takes `true` or `false`. For a file in the old format, run [`knott migrate`](../commands/migrate.md).

## Notes

As long as `name` itself is valid, the type is still registered, so one typo doesn't turn every entity into `entity-unknown-type`. A property definition that is unusable (unknown or missing `type`, missing `target`, not a mapping) is skipped. An invalid `required` or `description` falls back to its default (`false` / none), and the field stays active. A relation file with a valid `name` is registered too; a bad optional key is dropped.
