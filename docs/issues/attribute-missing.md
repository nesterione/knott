---
type: issue_code
code: attribute-missing
stage: attribute
about: "[Attribute](../concepts/attribute.md)"
---
# `attribute-missing`

A `required: true` attribute is absent, `null`, or an empty string.

## Example

```yaml
type: script
# title is required but missing
```

## Fix

Add the attribute with a real value.

## Notes

When the key is present but empty, the issue points at its line; when it's absent there is no line to point at.

A required field inside an object is reported with its full path, e.g. `senses[0].id`, at the line of the object it is missing from. A required `list` given `[]` is missing too.
