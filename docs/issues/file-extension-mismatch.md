---
type: issue_code
code: file-extension-mismatch
stage: file
about: "[File](../concepts/file.md)"
---
# `file-extension-mismatch`

The file exists, but its extension is not one the property's `accept` lists.

## Example

```yaml
# concept: audio: { type: file, accept: [mp3, wav] }
audio: ../audio/episode-42.flac
```

## Fix

Point at a file of an accepted type, or add the extension to `accept` in the concept file.

## Notes

Only the name is compared, without regard to case; knott does not open the file. A name with no dot, or only a leading one (`.env`), has no extension. `accept` is not checked for a URI.
