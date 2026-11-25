---
type: issue_code
code: relation-cycle
stage: relation
about: "[Relation](../concepts/relation.md)"
---
# `relation-cycle`

Following the links of an `acyclic: true` relation leads back to where it started. The message names one cycle.

## Example

```yaml
# decisions/0011.md
supersedes: "[0012](0012.md)"
# decisions/0012.md
supersedes: "[0011](0011.md)"
```

```
✗ decisions/0011.md:4  supersedes
  `supersedes` must not form a cycle: decisions/0011.md → decisions/0012.md → decisions/0011.md
  remove one of these `supersedes` references
```

An entity that references itself is a cycle too: `decisions/0013.md → decisions/0013.md`.

## Fix

Remove the reference that is wrong. For `supersedes` and `amends`, the newer entity is the source, so the older one should not point back.

## Notes

- One graph per relation: every property that names it counts, at any depth, in any concept. A cycle through `supersedes` and `amends` together is not reported.
- Only references that pass every check count. A reference with the wrong target type adds no edge; it is reported as [`relation-target-type-mismatch`](relation-target-type-mismatch.md).
- One issue per set of entities that lead back to each other, at the first entity on the named cycle, at its reference to the next one. The loop named is the shortest one from the entity with the smallest path.
- A scoped run (`knott validate some/file.md`) reports a cycle when one of its entities is in scope.
