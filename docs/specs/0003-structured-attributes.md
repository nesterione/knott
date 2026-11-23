---
type: spec
title: "0003: Add list, object and map attributes"
status: implemented
created_on: 2026-10-19
released_in: "0.4.0"
github_issues:
  - 3
decisions:
  - "[0008](../decisions/0008-structured-attributes.md)"
  - "[0005](../decisions/0005-empty-values.md)"
  - "[0004](../decisions/0004-strict-typing.md)"
concepts:
  - "[Attribute](../concepts/attribute.md)"
  - "[Schema](../concepts/schema.md)"
amends:
  - "[0001](0001-ontology-viewer.md)"
---
# 0003: Add list, object and map attributes

## Summary

A schema can declare lists, objects with named fields, and maps with free string keys and typed values, nested to any depth. Validation checks every nested value and reports its exact path (`senses[1].ru`, `forms.sg.acc`) and line. `knott types --verbose` now lists each type's attributes and relations. Existing scalar schemas, issue codes and messages are unchanged.

## Behaviour

### Schema syntax

An attribute's `type` is a scalar type or one of `list`, `object`, `map`. Each compound kind nests its inner definition under one key:

```yaml
type: lexeme
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
  forms:
    type: map
    values:
      type: map
      values: {type: string}
```

| Kind | Allowed keys |
|---|---|
| scalar | `type`, `required`*, `description` |
| `list` | `type`, `required`*, `description`, `items` (required) |
| `object` | `type`, `required`*, `description`, `fields` (required, at least one field) |
| `map` | `type`, `required`*, `description`, `values` (required) |

\* `required` is not allowed on an `items` or `values` node.

- `items` and `values` are definitions. `fields` maps names to definitions with the same keys as top-level attributes.
- There is no depth limit beyond the YAML loader's node cap, no string shorthand (`list of string`), and no named, reusable shapes.
- `type` is reserved as an attribute name only at the top level. A nested object field may be called `type`.
- Field names must be strings.

The loader reports each of these as `schema-invalid-field` at the exact key and line:

- a `list` without `items`, a `map` without `values`, an `object` without `fields` or with empty `fields`
- `items`, `fields` or `values` on the wrong kind
- `required` on `items` or `values`
- an unknown attribute type; the message lists the scalar types plus `list`, `object`, `map`

### Validating values

Every value is checked against its definition, recursively:

- **Scalars** use the existing type check ([0004](../decisions/0004-strict-typing.md)), with the nested value's raw text, so the boolean spelling rule applies at any depth.
- **Lists**: each item is checked against `items`.
- **Objects are closed.** Each declared field is checked. An undeclared key is `attribute-unknown-field`, listing the allowed fields and suggesting a close match.
- **Maps**: keys must be strings; each value is checked against `values`. A non-string YAML key (`1:`, unquoted `yes:`) is `attribute-type-mismatch` with a hint to quote it.
- **A value of the wrong kind** (`senses: "friend"`) is reported once, without checking its contents. Every other problem is reported.

### Empty values

[0005](../decisions/0005-empty-values.md) applies at every level, extended to containers:

| Value | Result |
|---|---|
| `null`, `""` | absent |
| `[]` for a `list`, `{}` for an `object` or `map` | absent, so a required list needs at least one item |
| `[]` or `{}` for a scalar or a container of the other kind | `attribute-type-mismatch` (`title: []`, `tags: {}`) |
| an empty list item or map value (`[a, null]`, `{nom: ~}`) | `attribute-type-mismatch`; an item is never absent |

An absent required attribute or field is `attribute-missing`.

### Issue location

`field` is the full path: list indexes in brackets, object fields and map keys after dots (`senses[1].ru`, `forms.sg.acc`). `line` points at the nested key or list item. Top-level fields look as before.

```
✗ lexemes/bad.md:4  tags[1]
  attribute `tags[1]` is an empty list item; remove it or give it a value

✗ lexemes/bad.md:7  senses[1].id
  required attribute `senses[1].id` (string) is missing or empty

✗ lexemes/bad.md:7  senses[1].ru
  attribute `senses[1].ru` expects string but got integer `5`; quote the value (e.g. "5") to make it a string

✗ lexemes/bad.md:7  senses[1].rus
  unknown field `rus` in attribute `senses[1]`; allowed fields: id, ru; did you mean `ru`?

✗ lexemes/bad.md:8  forms
  attribute `forms` has map key `1`, which YAML reads as integer; map keys must be strings; quote the key, e.g. "1"

✗ lexemes/bad.md:9  forms.sg.acc
  attribute `forms.sg.acc` is an empty map value; remove it or give it a value

✗ lexemes/other.md:5  senses
  attribute `senses` expects list of object but got string `friend`
```

A required list given `[]`: ``required attribute `senses` (list of object) is missing or empty; add at least one item``.

### Display

One compact notation is used by `types --verbose` and `view`: `string`, `list of string`, `list of object`, `map of map of string`, `object`. Object fields are indented under their attribute, and `*` marks a required one.

## Issue codes

| Code | Stage | When | `field` | `line` |
|---|---|---|---|---|
| `attribute-unknown-field` (new) | entity | a key not declared by an `object` shape | full path of the unknown key | that key |
| `attribute-missing` (changed) | entity | also for nested required fields and empty required containers | full path | nested key or item |
| `attribute-type-mismatch` (changed) | entity | also nested values, wrong-kind containers, empty items/values, non-string map keys | full path (the map for a bad key) | nested key or item |
| `schema-invalid-field` (changed) | schema | also the nesting errors above | full schema key path | that key |

## CLI and API

`knott types --verbose` now prints attributes and relations under each type:

```
$ knott types --verbose
lexeme  (.knott/schemas/lexeme.yaml)
  A word with its senses and forms.
  attributes:
    lemma*   string
    tags     list of string
    senses*  list of object
      each item: One sense per meaning.
      id*  string
      ru*  string  Russian gloss
    forms    map of map of string
  relations:
    topic*  → topic
    see     → ghost (undefined type)
```

A relation to a type no schema defines is marked `(undefined type)`. Types are separated by a blank line. `knott types` without `--verbose` is unchanged.

`knott view`: the side panel shows each attribute's notation, with object fields indented under it.

Python: `OntologyAttribute` mirrors the shape recursively.

```python
class OntologyAttribute(_Frozen):
    name: str | None          # None for items and values nodes
    type: str                 # scalar name, or "list" / "object" / "map"
    required: bool
    description: str | None
    items: OntologyAttribute | None = None
    values: OntologyAttribute | None = None
    fields: list[OntologyAttribute] = []
```

A scalar attribute serialises as before, plus the empty defaults.

## Edge cases

- `senses: "friend"` for a `list of object`: exactly one `attribute-type-mismatch`.
- `title: []` for a string: `attribute-type-mismatch`, not absent.
- `tags: []` for an optional list: absent, no issue.
- `{nom: ~}` in a map: the map value is reported, even when the map itself is optional.
- A nested boolean written `yes`: rejected as at the top level.
- An unknown key with no close match: the allowed fields are listed without a suggestion.
- A nested field named `type`: allowed. A top-level attribute named `type`: `schema-field-conflict`, as before.

## Out of scope

- References inside structured values; they wait for stable identifiers (#2) and the read API (#9).
- `min_items` / `max_items`.
- Named, reusable shapes and restricting map keys to a known set; both belong with enums (#4).

## Compatibility

Additive. Scalar schemas load unchanged, and scalar issues keep their codes, messages and `--format json` output. `OntologyAttribute.name` is now `str | None`, and the model gains `items`, `values` and `fields`. Released in 0.4.0.
