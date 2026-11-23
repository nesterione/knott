---
type: issue_code
code: relation-invalid-value
stage: relation
about: "[Reference resolution](../concepts/reference-resolution.md)"
---
# `relation-invalid-value`

A reference value has the wrong shape, or a reference isn't a valid plain path or Markdown link.

Wrong shape ([cardinality](../concepts/relation.md)): a list where `type: reference` holds one, a single string where a `list` of references is declared, `[]` on a single reference, an empty list item, or a value that isn't a string. Bad reference: a URL, a `#fragment`, an absolute path, a destination not ending in `.md`, a wikilink, an unencoded space in a link destination, or a `kid:` that isn't a canonical UUID.

## Example

```yaml
# concept: derived_from is a reference, sources a list of references
derived_from:                         # expects one reference but got a list
  - ../scripts/a.md
sources: ../scripts/a.md              # write it as a list of references, even for one
derived_from: [[episode-42]]          # unquoted wikilink = nested list
derived_from: https://example.com/a.md
derived_from: ../a.md#intro
```

## Fix

Match the declared shape: one value for `reference`, a list for a `list` of references. If several values are meant where one is declared, change the property to a `list` of references. Write each reference as a relative path to a `.md` file, preferably as a quoted Markdown link: `"[Episode 42](../scripts/episode-42.md)"`. Spaces need `<…>` or `%20`.
