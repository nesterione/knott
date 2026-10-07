---
type: issue_code
code: relation-invalid-value
stage: relation
about: "[Reference resolution](../concepts/reference-resolution.md)"
---
# `relation-invalid-value`

A relation value isn't a string or list of strings, or a reference isn't a valid plain path or Markdown link: a URL, a `#fragment`, an absolute path, a destination not ending in `.md`, a wikilink, or an unencoded space in a link destination.

## Example

```yaml
derived_from: [[episode-42]]          # unquoted wikilink = nested list
derived_from: https://example.com/a.md
derived_from: ../a.md#intro
```

## Fix

Use a relative path to a `.md` file, preferably as a quoted Markdown link: `"[Episode 42](../scripts/episode-42.md)"`. Spaces need `<…>` or `%20`.
