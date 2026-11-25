---
type: issue_code
code: schema-property-redefined
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-property-redefined`

A concept declares a property that one of its ancestors already declares. A child can only add properties.

## Example

```yaml
# .knott/concepts/tool.md; `concept` already declares `title`
name: tool
extends: concept
properties:
  title: { type: string }
```

## Fix

Remove the property from the child. If the child needs it different (optional here, required there), the property does not belong on the parent: move it to the children that have it.

## Notes

Reported on the child, at the line of its property, also when the parent gained the property later. The child's definition is dropped and the inherited one stands. Two children of one parent may each declare a property with the same name.
