---
type: issue_code
code: entity-invalid-frontmatter
stage: entity
about: "[Frontmatter](../concepts/frontmatter.md)"
---
# `entity-invalid-frontmatter`

A Markdown file starts with `---` but its frontmatter can't be used: invalid YAML, not a mapping, no closing `---`, invalid characters, or not UTF-8.

## Example

```yaml
derived_from: [Episode 42](../scripts/foo.md)   # unquoted link
```

## Fix

Fix the YAML. If the failing line holds a Markdown link, quote it: `"[Episode 42](../scripts/foo.md)"`.

## Notes

Knott can't tell whether the file was meant to be an entity, so it reports instead of skipping silently.
