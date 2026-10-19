---
type: concept
title: Attribute
summary: A typed value that belongs to the entity itself (a scalar, list, object or map), declared under `attributes:` in its schema.
spec_section: "§8"
related:
  - "[Schema](schema.md)"
  - "[Frontmatter](frontmatter.md)"
---
# Attribute

An attribute is a scalar, or a **list**, **object** or **map** built from scalars and nested to any depth.

## Scalars

Typing is strict. There is no coercion beyond this table:

| Type | Accepts | Rejects |
|---|---|---|
| `string` | YAML strings | numbers, booleans, dates (unquoted `42`, `no`, `2026-10-06`) |
| `integer` | YAML integers | booleans, floats |
| `number` | integers and floats | booleans |
| `boolean` | `true` / `false` | everything else, including `yes`/`no`/`on`/`off` |
| `date` | YAML date, or `"2026-10-06"` | datetimes |
| `datetime` | YAML timestamp, or ISO 8601 string with a time | plain dates |

## Lists, objects and maps

```yaml
attributes:
  tags:
    type: list
    items: {type: string}
  senses:
    type: list
    required: true
    items:
      type: object
      description: One sense per meaning.
      fields:
        id: {type: string, required: true}
        ru: {type: string, required: true, description: Russian gloss}
  forms:                    # forms.sg.nom, forms.pl.gen, …
    type: map
    values:
      type: map
      values: {type: string}
```

| `type` | Holds | Nested key |
|---|---|---|
| `list` | a YAML sequence; every item matches `items` | `items` (a definition) |
| `object` | a YAML mapping with exactly the declared keys | `fields` (name → definition) |
| `map` | a YAML mapping with free string keys; every value matches `values` | `values` (a definition) |

- Object fields take `type`, `required` and `description`, like top-level attributes. A field may be named `type`.
- `items` and `values` take `type` and `description`, but not `required`.
- Objects are **closed**: an undeclared key is `attribute-unknown-field`. Use a `map` when the keys are free.
- Map keys must be strings; quote keys that YAML would read as numbers or booleans.
- Problems name the exact location, e.g. `senses[1].ru` or `forms.sg.acc`, with its line.

See [decision 0008](../decisions/0008-structured-attributes.md).

## Absent values

A key that is present with `null` or an empty string counts as **absent**. So does an empty container of the declared kind: `[]` for a list, `{}` for an object or map. `required: true` means present and not empty, so a required list needs at least one item. An empty container of another kind (`title: []`) is a type mismatch. A list item or map value is never absent. See [decision 0005](../decisions/0005-empty-values.md).

Not supported yet: enums, unions, relations inside structured values, item counts, custom scalars.
