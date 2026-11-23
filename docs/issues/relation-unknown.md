---
type: issue_code
code: relation-unknown
stage: schema
about: "[Relation](../concepts/relation.md)"
---
# `relation-unknown`

A reference property in a concept file names a relation that no file in `.knott/relations/` defines.

## Example

```yaml
# .knott/concepts/decision.md; .knott/relations/ has about, related and supersedes
properties:
  supersedes: { type: reference, target: decision, relation: replaces }
```

```
✗ .knott/concepts/decision.md:5  properties.supersedes.relation
  `properties.supersedes.relation` names relation `replaces`, which no relation file in `.knott/relations/` defines (known relations: `about`, `related`, `supersedes`); the reference still works as a plain reference
```

## Fix

Fix the name, or add `.knott/relations/replaces.md` with `name: replaces`. `knott types --verbose` lists the relations that loaded.

## Notes

Until it's fixed, the property is a plain reference: its values are still resolved and type-checked, `knott refs` groups it by property path, and `types --verbose` shows no relation for it.
