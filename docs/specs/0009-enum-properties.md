---
type: spec
title: "0009: Enum properties"
status: implemented
created_on: 2026-11-25
released_in: "0.8.0"
realizes:
  - "[Enumerated values](../intents/enumerated-values.md)"
decisions:
  - "[0004](../decisions/0004-strict-typing.md)"
  - "[0005](../decisions/0005-empty-values.md)"
  - "[0008](../decisions/0008-structured-attributes.md)"
concepts:
  - "[Attribute](../concepts/attribute.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Ontology](../concepts/ontology.md)"
amends:
  - "[0005](0005-concept-files.md)"
---
# 0009: Enum properties

## Summary

A concept can declare a property of shape `enum`: a string that must be one of the options the concept lists. Each option can carry a short description. A value outside the set is reported with the allowed options, and `knott types --verbose`, `knott view` and the agent skill show the options, so an agent can pick a correct value before it writes the file. The change is additive.

## Behaviour

### The `enum` shape

```yaml
# .knott/concepts/lexeme.md
---
name: lexeme
properties:
  gender: { type: enum, options: [m, f] }
  level:
    type: enum
    required: true
    description: CEFR level at which the word is taught.
    options:
      A1: Understands and uses familiar everyday expressions.
      A2: Handles simple, routine exchanges.
      B1:
  tags:
    type: list
    items: { type: enum, options: [colloquial, formal, archaic] }
---
```

- `enum` is allowed wherever a shape is: at the top level, as list `items`, as map `values`, or as an object field, at any depth. A list of enums is how an entity picks several.
- An `enum` definition has one key of its own, besides `required` and `description`:

  | Key | Required | Value |
  |---|---|---|
  | `options` | yes | the allowed values, in one of the two forms below. At least one. |

- The key is `options`, not `values`: `values` already holds the value definition of a `map`.
- **List form**: a list of strings. Use it when the options need no explanation.
- **Mapping form**: option → description. The description is a string, or empty when an option needs none. Options keep the order they are written in.
- An option is a non-empty string with no whitespace at either end. Options are compared exactly, so `A1` and `a1` are different options.
- `options` on any other shape is `schema-invalid-field` ("only allowed when `type` is enum"); on a `list` or `map` the message says to put it on `items` or `values`. An `enum` without `options` is `schema-invalid-field`, as a `list` without `items` is.
- In `options`, each of these is `schema-invalid-field`, at that option's line, and the property is not loaded:
  - an empty list or mapping;
  - an option that is not a string. YAML reads unquoted `no`, `yes`, `on`, `off` as booleans, `1` as an integer and `2026-10-06` as a date; the message says to quote it (`"no"`);
    in the mapping form such a key has no line of its own, so the issue is reported at `options`;
  - an empty option, or one with whitespace at either end;
  - the same option twice, in the list form;
  - a description that is not a string, in the mapping form.
- The same key twice in the mapping form cannot be detected: YAML keeps only the last one.

### Values

A value passes when it is a YAML string equal to one of the options. An `enum` is an attribute, with the `attribute-*` codes.

| Value | Result |
|---|---|
| `null` / `""` | absent ([0005](../decisions/0005-empty-values.md)); `attribute-missing` when the property is required |
| a string that is an option | valid |
| a string that is not an option | `attribute-unknown-option` |
| anything else: boolean, number, date, list, mapping | `attribute-type-mismatch`, as for `string` |

- Typing is strict ([0004](../decisions/0004-strict-typing.md)). For `options: ["yes", "no"]`, an entity that writes an unquoted `no` holds a boolean, so it is `attribute-type-mismatch`, with the hint to quote the value.
- The value is not trimmed and not case-folded: `gender: F` does not match the option `f`.
- In a list of enums, each item is checked on its own. The same option twice in one list is valid.

### The message

`attribute-unknown-option` names the value and lists every option, in the concept's order:

```
✗ lexemes/draugas.md:4  gender
  attribute `gender` must be one of `m`, `f`, but got `female`
```

It ends with `; did you mean …?` when one option is close. The rule, in order:

1. the one option that equals the value when case is ignored (`a1` → `A1`);
2. otherwise the closest option by the same matching the unknown-key messages use (`femnine` → `feminine`).

When neither finds one, the message has no suggestion: `female` suggests nothing for `m` and `f`. Option descriptions are not printed in the message; `knott types --verbose` shows them.

## Issue codes

| Code | Stage | When | `field` / `line` |
|---|---|---|---|
| `attribute-unknown-option` | attribute | a string value of an `enum` is not one of its options | the full path (`tags[2]`) / the value's line |

`schema-invalid-field` also covers the `options` key. `attribute-missing` and `attribute-type-mismatch` apply to an `enum` as they do to a `string`. No existing code changes meaning.

## CLI and API

### `knott validate`

Checks enum values at every nesting level. No change to its output or stats.

### `knott types --verbose`

An enum shows `enum` in the type column. Its options are printed under the property, indented by two more spaces, so a long set does not widen the table:

```
lexeme  (.knott/concepts/lexeme.md)
  template: no
  references: none
  properties:
    gender  enum
      one of: m | f
    level*  enum          CEFR level at which the word is taught.
      A1: Understands and uses familiar everyday expressions.
      A2: Handles simple, routine exchanges.
      B1
    tags    list of enum
      one of: colloquial | formal | archaic
```

- When no option has a description: one line, `one of: ` and the options joined by ` | `.
- When at least one has: one line per option, `<option>: <description>`, or the option alone. A description is printed on one line.
- For a list or map of enums, these lines follow the `each item:` or `each value:` line, when there is one.

### `knott view`

The property table shows `enum` and, under it, the options with their descriptions. The embedded data has `options` on each attribute.

### Python API

- `OntologyAttribute.type` may be `enum`. One field is added: `options: list[EnumOption]`, in the concept's order, `[]` for other shapes.
- `EnumOption(value: str, description: str | None)` is exported from `knott`.
- `OntologyAttribute.notation` is `enum`, or `list of enum`.

### Agent skill

The bundled skill says: read the options in `knott types --verbose` before writing an enum value, copy an option exactly, and quote one that YAML would read as a boolean, number or date.

## Edge cases

| Case | Result |
|---|---|
| `gender: female`, options `[m, f]` | `attribute-unknown-option`, no suggestion |
| `level: a1`, options `A1 … C2` | `attribute-unknown-option`; did you mean `A1`? |
| `gender: " f"` (quoted, with a space) | `attribute-unknown-option`; values are not trimmed |
| `gender:` or `gender: ""`, not required | absent, valid |
| `gender:` and `required: true` | `attribute-missing` |
| `answer: no`, options `["yes", "no"]` | `attribute-type-mismatch`: a boolean; quote the value |
| `answer: "no"`, options `["yes", "no"]` | valid |
| `level: 1`, options `["1", "2"]` | `attribute-type-mismatch`: an integer; quote the value |
| `gender: [m]`, a single enum | `attribute-type-mismatch`: a list |
| `tags: [formal, slang, formal]`, a list of enums | one `attribute-unknown-option` at `tags[1]`; the repeated `formal` is valid |
| `tags: formal`, a list of enums | `attribute-type-mismatch`, as for any list |
| `options: [yes, no]` in the concept | `schema-invalid-field` for each: YAML reads them as booleans; quote them |
| `options: [m, f, m]` | `schema-invalid-field`: `m` is listed twice |
| `options: []`, `options: {}`, or `options: m` | `schema-invalid-field` |
| `options: { A1: 3 }` | `schema-invalid-field`: the description must be a string |
| `type: enum` with no `options` | `schema-invalid-field` |
| `type: string` with `options` | `schema-invalid-field`: only allowed when `type` is enum |
| An enum with one option | valid |
| An option that contains spaces or punctuation (`"in review"`) | valid; the value must be written the same way |

## Out of scope

- A set defined once and used by several types. Each concept lists its own options. A shared set would be a definition file of its own, as relations and connectors are; a later spec.
- Options that are not strings: integers, dates, booleans.
- Matching that ignores case, and aliases for one option.
- Requiring that the items of a list are unique.
- Making a property required when an enum has a certain value: [issue #7](https://github.com/nesterione/knott/issues/7).
- A fix command that rewrites an unknown value.

## Compatibility

Additive. A concept that declared `type: enum` got `schema-invalid-field` before and is now an enum property. A vault without enum properties behaves exactly as in 0.7.0. Changing a property from `string` to `enum` makes existing entities with other values invalid; `knott validate` lists them. Ontology API additions only. Version 0.8.0.
