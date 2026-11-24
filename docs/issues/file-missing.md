---
type: issue_code
code: file-missing
stage: file
about: "[File](../concepts/file.md)"
---
# `file-missing`

A `required: true` file property is absent, null or empty. A required list or map of files needs at least one.

## Example

```yaml
# concept: audio: { type: file, required: true }
type: recording
audio:
```

## Fix

Give the property a path to a file in the vault, or a URI whose scheme is a declared connector.
