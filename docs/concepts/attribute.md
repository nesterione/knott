---
type: concept
title: Attribute
summary: A typed scalar value that belongs to the entity itself, declared under `attributes:` in its schema.
spec_section: "§8"
related:
  - "[Schema](schema.md)"
  - "[Frontmatter](frontmatter.md)"
---
# Attribute

Typing is strict. There is no coercion beyond this table:

| Type | Accepts | Rejects |
|---|---|---|
| `string` | YAML strings | numbers, booleans, dates (unquoted `42`, `no`, `2026-10-06`) |
| `integer` | YAML integers | booleans, floats |
| `number` | integers and floats | booleans |
| `boolean` | `true` / `false` | everything else, including `yes`/`no`/`on`/`off` |
| `date` | YAML date, or `"2026-10-06"` | datetimes |
| `datetime` | YAML timestamp, or ISO 8601 string with a time | plain dates |

## Absent values

A key that is present with `null` or an empty string counts as **absent**. `required: true` means present and not empty. (An empty list `[]` is *not* absent for an attribute; it's a type mismatch, because a list is never a valid scalar. See [decision 0005](../decisions/0005-empty-values.md).)

Not in v0: enums, unions, lists, nested objects, custom scalars.
