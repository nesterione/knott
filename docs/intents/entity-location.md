---
type: intent
title: Entity location
status: open
raised_on: 2026-11-25
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Entity](../concepts/entity.md)"
  - "[Vault](../concepts/vault.md)"
---
# Entity location

## Need

Most vaults keep each type in its own folder: specs in `specs/`, episodes in `episodes/<year>/`. The rule lives in a `CLAUDE.md` or in habit. Knott accepts an entity anywhere, so an agent that writes a spec into `notes/` passes `knott validate`, and the file is then missed by everyone who looks in `specs/`. An agent about to create an entity has nowhere to look up where it goes.

## Example

This vault keeps every `spec` in `docs/specs/`. With the folder declared in the concept, a spec saved as `intents/0011-entity-location.md` fails `knott validate` with a message that names `specs`, and `knott types --verbose` shows the folder before the agent writes the file. A podcast vault declares `episodes/*` so each episode sits in a year folder. A concept that declares nothing can live anywhere, as today.

## Open questions

Answered by [spec 0011](../specs/0011-entity-location.md). Left for a later spec:

- The reverse rule: a folder that may hold only entities of one type.
- A command that moves a misplaced entity and rewrites the links that point at it.
