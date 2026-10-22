---
type: issue_code
code: kid-duplicate
stage: kid
about: "[Kid](../concepts/kid.md)"
---
# `kid-duplicate`

Two or more entities have the same `kid`. Each `kid` must belong to exactly one entity in the vault.

## Example

```
✗ lexemes/draugas-copy.md:3  kid
  `kid` 3f2b8c1e-… is claimed by 2 entities: lexemes/draugas-copy.md:3, lexemes/draugas.md:3
```

## Fix

Usually one file was copied from the other. Delete the `kid:` line from the **copy**, then run `knott validate --fix` to give it a new one. Keep the original's `kid`, because other entities and tools may refer to it.

## Notes

- Reported once per duplicated value, on the first claimant by path. The message lists every claimant.
- `--fix` never changes a duplicate, because it can't tell which file is the original.
- A scoped run (`knott validate some/file.md`) reports a duplicate only if one of its claimants is in scope.
- Until it's fixed, `kid:` references to that value report `relation-target-ambiguous`.
