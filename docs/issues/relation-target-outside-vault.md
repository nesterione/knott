---
type: issue_code
code: relation-target-outside-vault
stage: relation
about: "[Reference resolution](../concepts/reference-resolution.md)"
---
# `relation-target-outside-vault`

A reference resolves to a path outside the vault root, either textually (`../../x.md`) or through a symlink that points out of the vault.

## Example

```yaml
derived_from: ../../outside.md
```

## Fix

Move the target into the vault, or drop the relation. Relations only connect entities in the same vault.
