---
name: supersedes
inverse: superseded_by
acyclic: true
description: This entity replaces the target entirely. The target is kept unchanged as history.
---
Use `supersedes` when the old record is no longer the current answer: a new decision reverses an old one, or a new spec replaces an old spec as a whole. The old file is never edited (decision 0011); `knott refs` on it lists the newer record under `superseded_by`.

When the old record still stands and only part of it changes, use `amends`. A chain of `supersedes` must not loop back on itself: knott reports `relation-cycle`.
