---
type: issue_code
code: file-invalid-value
stage: file
about: "[File](../concepts/file.md)"
---
# `file-invalid-value`

The value of a file property is not a usable path or URI.

## Example

```yaml
audio: [a.mp3, b.mp3]             # one file expected; declare a list for several
images: ../img/a.png              # a list expected, even for one
cover: "[cover](gdrive:1AbC)"     # a URI inside a Markdown link
slides: "gdrive:"                 # nothing after the scheme
notes: kid:3f2b8c1e-…             # an entity; use a reference property
data: /srv/data.json              # absolute path
clip: ../audio/take.mp3#t=30      # fragment
size: 42                          # not a string
```

## Fix

Write one string per file: a path relative to this file, or a URI on its own.

- Match the declared shape: `type: file` holds one value, a `list` of files holds a list.
- Put a caption for a URI in a field next to it; only a path can be a Markdown link.
- Write a file whose name has a colon with a leading `./` (`./a:b.json`).

## Notes

An unquoted `[[take.mp3]]` is read by YAML as a nested list. Wikilinks are not supported; use a quoted Markdown link.
