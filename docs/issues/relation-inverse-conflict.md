---
type: issue_code
code: relation-inverse-conflict
stage: schema
about: "[Relation](../concepts/relation.md)"
---
# `relation-inverse-conflict`

A relation's `inverse` can't name the link read from the target side, because the name is already taken:

| The `inverse` equals | Message says |
|---|---|
| another relation's `inverse` | both relations and their files |
| its own `name` | use `symmetric: true` |
| another relation's `name` | that relation and its file |
| a top-level property of a concept this relation can point at | the concept and its file |

## Example

```yaml
# .knott/relations/about.md; concept files have a `title` property
---
name: about
inverse: title
---
```

```
✗ .knott/relations/about.md:3  inverse
  inverse `title` of relation `about` is also a property of concept `concept` (`.knott/concepts/concept.md`), which this relation can point at; reading the link from the target side would be ambiguous
```

## Fix

Choose another `inverse`, usually a past participle or a phrase such as `superseded_by` or `discussed_in`. For a link that reads the same both ways, drop `inverse` and write `symmetric: true`.

## Notes

- Reported at the `inverse:` line. For two relations with the same `inverse`, it is the second file by path.
- Only top-level property names conflict. A nested field such as `speakers[].role` doesn't, and neither does a property of a concept the relation's properties can't target.
