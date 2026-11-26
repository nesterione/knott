---
type: intent
title: Included folders
status: open
raised_on: 2026-11-26
concepts:
  - "[Vault](../concepts/vault.md)"
  - "[Entity](../concepts/entity.md)"
---
# Included folders

## Need

Knott reads every `*.md` file under the vault root. A vault is often the root of a repository that holds more than knowledge: vendored packages, build output, test fixtures, generated Markdown, a `node_modules/` or a `venv/`. Their files are read on every run, which is slow, and a file there that happens to have `type` in its frontmatter is reported as an entity of an unknown type. Only folders whose name starts with `.` are skipped, and the user cannot rename the others. Today the only way out is to move `.knott/` into a subfolder, which changes the vault root and puts every other folder out of reach.

## Example

A repository with `.knott/` at its root keeps knowledge in `docs/` and `notes/`, code in `src/`, and test vaults in `tests/fixtures/`. The fixtures are full of deliberately broken entities, so `knott validate` fails on them. With the two knowledge folders named once in the vault's configuration, every command sees only `docs/` and `notes/`: the fixtures are not read, the run is faster, and the entity counts are those of the knowledge base. A vault that names nothing behaves as today.

## Open questions

Answered by [spec 0019](../specs/0019-included-folders.md). Left for a later spec:

- Excluding a folder inside a scanned one, patterns, and reading `.gitignore`.
- Including a hidden folder.
