---
type: decision
title: Relations are stored only on the source side
status: accepted
decided_on: 2026-10-06
affects: "[Relation](../concepts/relation.md)"
---
# 0003: Relations are stored only on the source side

**Decision.** A relation is declared in the source type's schema and stored in the source entity. The target gets no inverse.

**Why.** Storing both directions duplicates state that drifts out of sync, and makes ownership unclear: which side do you edit?

**Consequences.** "What points at this script?" is answered by tools: Obsidian backlinks today, a derived index later. Explicit inverse relations may come later if real workflows need them.
