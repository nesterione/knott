---
type: issue_code
code: attribute-type-mismatch
stage: attribute
about: "[Attribute](../concepts/attribute.md)"
---
# `attribute-type-mismatch`

An attribute's value doesn't match its declared scalar type. Typing is strict, with no coercion.

## Example

```yaml
title: no          # boolean, not string
count: true        # boolean, not integer
day: 2026-10-06 10:30:00   # datetime, not date
flag: yes          # not true/false
```

## Fix

Quote values YAML would read as something else (`"no"`, `"42"`, `"2026-10-06"`), and write booleans as `true`/`false`. The message names the expected and actual type.
