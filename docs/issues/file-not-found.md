---
type: issue_code
code: file-not-found
stage: file
about: "[File](../concepts/file.md)"
---
# `file-not-found`

No file exists at the resolved path with exactly that case, or the path names a folder.

## Example

```yaml
audio: ../audio/Take.mp3   # real file: audio/take.mp3
cover: ../img              # a folder
```

## Fix

Fix the path. It is relative to the file that contains it, and case must match exactly, even on macOS. The message shows the vault-relative path it resolved to.

## Notes

Often caused by moving or renaming the file. Knott does not track which entities point at a file.
