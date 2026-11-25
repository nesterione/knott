---
type: issue_code
code: schema-unknown-parent
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-unknown-parent`

The concept's `extends` names a type that no concept file defines. A parent whose own file has errors and did not load counts too.

## Example

```yaml
# .knott/concepts/tool.md
name: tool
extends: concpt
```

## Fix

Correct the name, or add the parent's concept file. The message lists the known types and suggests a close one.

## Notes

Reported at the line of `extends`. The concept still loads, as a root type: it inherits nothing, and a reference that targets the intended parent does not accept its entities, so more issues may follow until this one is fixed.
