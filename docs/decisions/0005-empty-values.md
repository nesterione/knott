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

| Value | Attribute | Relation |
|---|---|---|
| `null` / blank | absent | absent |
| `""` | absent | absent |
| `[]` | **type mismatch** | absent |

**Why.** `[]` is the list form of "empty", and only relations take lists. For an attribute, a list is never a valid scalar, so `title: []` is reported as a mismatch instead of silently passing as "missing". The first implementation treated `[]` as absent everywhere; this was changed after review.

**Consequences.** A blank optional field never fails. A required one reports `attribute-missing` / `relation-missing`, pointing at the key's line when the key is present.
