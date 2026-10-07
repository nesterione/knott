---
type: decision
title: Markdown files are the source of truth
status: accepted
decided_on: 2026-10-06
affects:
  - "[Vault](../concepts/vault.md)"
  - "[Entity](../concepts/entity.md)"
---
# 0001: Markdown files are the source of truth

**Context.** Knowledge bases built for agents tend to drift into databases that humans can't inspect.

**Decision.** All data lives in Markdown files with YAML frontmatter. Knott keeps no state of its own: `validate` and `types` never write a file, and there is no index, cache, or database. Any future index must be derived and rebuildable from the files.

**Consequences.** A vault works with a file manager, any editor, Obsidian, and Git diffs, with or without Knott installed. Every run re-reads the files, which is fine at v0 scale.
