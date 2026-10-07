---
type: decision
title: Symlinks cannot take a relation outside the vault
status: accepted
decided_on: 2026-10-06
affects:
  - "[Reference resolution](../concepts/reference-resolution.md)"
  - "[Vault](../concepts/vault.md)"
---
# 0006: Symlinks cannot take a relation outside the vault

**Context.** References are resolved *lexically*: `../` means what the file tree shows. But a lexically valid path such as `linked/b.md` can pass through a symlinked directory that points outside the vault.

**Decision.** After the lexical check, Knott also resolves the real path. If it leaves the vault root, the reference fails with `relation-target-outside-vault`. Symlinks that stay inside the vault are fine.

**Why.** Discovery already refuses to follow symlinked directories, so a target reachable only through one isn't part of the vault. Found in code review.

**Known gap.** A symlinked *file* inside the vault that points outside is still discovered as an entity (the spec forbids only following symlinked directories), but it can't be a relation target.
