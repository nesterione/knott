---
type: issue_code
code: file-outside-vault
stage: file
about: "[File](../concepts/file.md)"
---
# `file-outside-vault`

The path leaves the vault root, directly or through a symlink.

## Example

```yaml
audio: ../../shared/episode-42.mp3
```

## Fix

Move the file into the vault, or keep it in a store and write its URI (`s3://…`).

## Notes

The check is the one references use; see [decision 0006](../decisions/0006-symlinks-and-containment.md).
