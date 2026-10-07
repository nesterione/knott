---
type: concept
title: Relation
summary: A typed, directed reference from one entity to another, stored as a relative path on the source side only.
spec_section: "§9–11"
related:
  - "[Entity](entity.md)"
  - "[Schema](schema.md)"
  - "[Reference resolution](reference-resolution.md)"
---
# Relation

```
transcript ── derived_from ──▶ script
```

A relation is declared in the **source** type's schema, under `relations:`, with a `target` type. There is no global relation registry, and only declared keys are relations: an undeclared key that happens to look like a path is ordinary metadata.

## Value shape

One reference, or a list of them:

```yaml
derived_from: ../scripts/episode-42.md                      # plain path
derived_from: "[Episode 42 script](../scripts/episode-42.md)" # Markdown link (recommended)
sources:
  - ../scripts/episode-42.md
  - "[Notes](<../notes/my notes.md>)"
```

`null`, `""` and `[]` count as absent. A `required: true` relation needs at least one reference.

## Source side only

The target never stores the inverse. A script does not list its transcripts. This avoids duplicated state that drifts out of sync. Reverse navigation comes from tools (Obsidian backlinks) or a future derived index.

How each reference is checked: [reference resolution](reference-resolution.md).
