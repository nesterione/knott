---
type: decision
title: Structured attributes use explicit keywords, and objects are closed
status: accepted
decided_on: 2026-10-19
affects:
  - "[Attribute](../concepts/attribute.md)"
  - "[Schema](../concepts/schema.md)"
---
# 0008: Structured attributes use explicit keywords, and objects are closed

**Context.** Real entities hold more than scalars: tags, the senses of a word, an inflection table, review annotations. Schemas could only describe scalars, so this data stayed undeclared, and undeclared keys are never checked (GitHub issue #3).

**Decision.**

- An attribute's `type` can also be `list` (with `items`), `object` (with `fields`) or `map` (with `values`). `items` and `values` are themselves definitions. `fields` maps names to definitions, using the same `type` / `required` / `description` keys as top-level attributes. Shapes nest without a depth limit. There is one form only, with no `list of string` shorthand and no JSON Schema vocabulary.
- **Objects are closed.** A key that a declared object doesn't list is reported as `attribute-unknown-field`, with a "did you mean" suggestion. `map` is the open form: its keys are free, but they must be strings.
- `items` and `values` take a `description` but not `required`. A list item or map value is never empty, and "at least one item" is `required` on the list itself.
- `type` may name a nested field. It is reserved only at the top level, where it names the entity type.
- Nested problems reuse `attribute-missing` and `attribute-type-mismatch`. `field` holds the full path (`senses[1].ru`, `forms.sg.acc`), and `line` points at the nested key or item. A value of the wrong kind is reported once, without checking its contents.
- Empty values follow [0005](0005-empty-values.md) at every level.

**Not included.** Relations inside structured values; they wait for stable identifiers (#2) and the read API (#9). Item counts (`min_items` / `max_items`). Named, reusable shapes; those will be decided together with reusable enum value sets (#4). Restricting map keys to a known set (an enum concern, #4).

**Why.** Keywords nest the same way at every level, and an agent can read them without learning a mini-language. Closed objects exist because a misspelled nested key slipping through is exactly the problem this solves. Map keys are strings because issue paths and Obsidian both assume them.

**Consequences.** Obsidian's property editor shows nested values as raw YAML; lists of text still edit natively. `knott types --verbose` and `knott view` show shapes in a compact form (`list of object`, `map of map of string`) with object fields indented below.
