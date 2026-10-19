---
type: decision
title: What counts as an empty value
status: accepted
decided_on: 2026-10-06
affects:
  - "[Attribute](../concepts/attribute.md)"
  - "[Relation](../concepts/relation.md)"
---
# 0005: What counts as an empty value

**Context.** Obsidian templates leave properties blank, so `title:` (null) is common. The spec says a null or empty value counts as absent, and for relations explicitly adds `[]`.

**Decision.**

| Value | Scalar attribute | `list` attribute | `object` / `map` attribute | Relation |
|---|---|---|---|---|
| `null` / blank | absent | absent | absent | absent |
| `""` | absent | absent | absent | absent |
| `[]` | **type mismatch** | absent | **type mismatch** | absent |
| `{}` | **type mismatch** | **type mismatch** | absent | invalid value |

The rule is: an empty container *of the declared kind* is absent, and one of another kind is a mismatch. It applies at every nesting level, with one exception: a list item or map value is never absent, so `tags: [a, null]` and `forms: {nom: ~}` are reported as mismatches.

**Why.** `[]` is the list form of "empty", and only relations take lists. For an attribute, a list is never a valid scalar, so `title: []` is reported as a mismatch instead of silently passing as "missing". The first implementation treated `[]` as absent everywhere; this was changed after review.

**Amended 2026-10-19** by [0008](0008-structured-attributes.md): attributes can now be lists, objects and maps, so the table gained their columns and the `{}` row. The scalar column is unchanged.

**Consequences.** A blank optional field never fails, and a `required` list needs at least one item. A required one reports `attribute-missing` / `relation-missing`, pointing at the key's line when the key is present.
