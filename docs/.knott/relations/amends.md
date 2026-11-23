---
name: amends
inverse: amended_by
acyclic: true
description: This entity changes part of the target. The target still stands for everything this entity does not change.
---
Use `amends` when the old record stays mostly valid: a new decision adjusts one rule of an earlier one, or a new spec adds to or changes part of an implemented spec. The old file is never edited (decision 0011); `knott refs` on it lists the newer record under `amended_by`, so a reader of the old record knows to read both.

When the new record replaces the old one entirely, use `supersedes`. A chain of `amends` must not loop back on itself: knott reports `relation-cycle`.
