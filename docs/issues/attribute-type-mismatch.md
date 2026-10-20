---
type: issue_code
code: attribute-type-mismatch
stage: attribute
about: "[Attribute](../concepts/attribute.md)"
---
# `attribute-type-mismatch`

An attribute's value doesn't match its declared type. Typing is strict, with no coercion.

## Example

```yaml
title: no          # boolean, not string
count: true        # boolean, not integer
day: 2026-10-06 10:30:00   # datetime, not date
flag: yes          # not true/false
```

## Fix

Quote values YAML would read as something else (`"no"`, `"42"`, `"2026-10-06"`), and write booleans as `true`/`false`. The message names the expected and actual type.

## Structured values

Nested values are checked the same way, and the issue's `field` is the full path: `senses[1].ru`, `forms.sg.acc`. A value of the wrong kind (a string where a `list` is declared) is reported once, without checking its contents. An empty list item or map value (`tags: [a, null]`), and a map key that isn't a string, are also reported with this code.
