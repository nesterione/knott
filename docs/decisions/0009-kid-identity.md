---
type: decision
title: Entities get a knott-managed `kid`
status: accepted
decided_on: 2026-10-22
affects:
  - "[Kid](../concepts/kid.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
---
# 0009: Entities get a knott-managed `kid`

**Context.** Things outside the vault (learning progress, review history, logs, other tools) need to know *which* entity is meant. A file path changes whenever a file is moved or renamed (GitHub issue #2). [0002](0002-relative-paths-not-ids.md) chose paths for relations and left room for an identifier scheme behind `resolve_reference()`.

**Decision.**

- **`kid`** is a reserved top-level frontmatter key on every entity, like `type`. Its value is a canonical lowercase UUID (`8-4-4-4-12` hex, any version). Knott generates v4. The key is namespaced so it doesn't collide with an `id` a vault already uses for its own purposes.
- It is **optional** unless a schema says `kid: required`. When present, it is always checked: format (`kid-invalid`) and global uniqueness (`kid-duplicate`).
- **Knott manages it.** `knott validate --fix` inserts `kid: <uuid4>` into every in-scope entity that has no `kid` key. It is a single inserted line, re-parsed before it is written; the rest of the file is byte-for-byte unchanged. This is knott's only edit to user files. Any future command that creates an entity will write a `kid` too.
- Relations may refer to an entity as **`kid:<uuid>`**. **Markdown links stay the default and recommended form**; `kid:` is for references that must survive renames. Both forms go through `resolve_reference()` and the same entity and type checks.
- **Duplicates are reported, never auto-fixed.** The usual cause is a copied file. Knott can't tell the original from the copy, and re-keying the wrong one would silently break references to it. A `kid:` reference to a duplicated value is `relation-target-ambiguous`.
- The `kid` index is built lazily, once per run. A scoped run reports a duplicate only when one of its claimants is in scope.

**Why not a human-written slug?** A readable `id: restoranas` would also catch an agent creating the same concept twice. We chose knott-managed UUIDs so that identity takes no authoring effort and never collides with existing keys. The trade-off: **a UUID does not detect duplicate concepts.** Two `restoranas` lexemes get two different `kid`s. That needs natural-key uniqueness (e.g. `unique: true` on `lemma`), tracked separately.

**Consequences.** `kid:` references aren't clickable in Obsidian; a Markdown link next to them is. Copying a file copies its `kid`, so the agent skill says to delete that line from the copy and run `--fix`. Tools outside the vault should store the `kid`, not the path.
