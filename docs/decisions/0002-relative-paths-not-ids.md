---
type: decision
title: Relations use relative paths, not IDs
status: accepted
decided_on: 2026-10-06
affects:
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
---
# 0002: Relations use relative paths, not IDs

**Context.** Stable IDs survive renames, but they're opaque, need a mapping, and aren't clickable.

**Decision.** v0 references are relative filesystem paths (plain, or as a Markdown link). Wikilinks are rejected because they resolve by name, not path.

**Consequences.** Links are human-readable, clickable in Obsidian, and Git-friendly. Renames can break them, so Knott reports `relation-target-not-found` and Obsidian's link updating covers the common case. All resolution sits behind one function, `resolve_reference()`, so an `id:` scheme can be added later in one place.

**Amended 2026-10-22** by [0009](0009-kid-identity.md): relations may also be written `kid:<uuid>`, resolved through the same function. Relative paths, and Markdown links in particular, remain the default and recommended form.
