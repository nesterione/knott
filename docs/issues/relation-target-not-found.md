---
type: issue_code
code: relation-target-not-found
stage: relation
about: "[Reference resolution](../concepts/reference-resolution.md)"
---
# `relation-target-not-found`

No file exists at the resolved path, with exact case matching.

## Example

```yaml
derived_from: ../Scripts/Episode-42.md   # real file: scripts/episode-42.md
```

## Fix

Fix the path. It's relative to the file containing it, and case must match exactly, even on macOS. The message shows the vault-relative path it resolved to.

## Notes

Often caused by a file move. In Obsidian, use the relative-path link settings so links are updated on rename.
