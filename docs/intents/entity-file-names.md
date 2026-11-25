---
type: intent
title: Entity file names
status: open
raised_on: 2026-11-25
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Entity](../concepts/entity.md)"
---
# Entity file names

## Need

File names carry meaning: a number that orders specs, a date that orders episodes, a slug people recognise in a link. Each type has its own convention, and today it is written in a template comment or a `CLAUDE.md`. Knott checks none of it, so `Loops spec.md` sits next to `0009-enum-properties.md`. An agent has to guess both the shape of the name and how to fill each part of it: what the number is, how long the slug should be.

## Example

This vault names specs `NNNN-<slug>.md`. With the pattern declared in the concept, `specs/loops.md` fails `knott validate`. `knott types --verbose` shows the pattern and, for each part, what is allowed and how to choose it ("the next free number in `specs/`", "the change in two to five lowercase words"), so an agent names the file correctly the first time.

## Open questions

Answered by [spec 0012](../specs/0012-entity-file-names.md). Left for a later spec:

- A part whose value must equal a property of the entity, such as `{created_on}`.
- Parts that knott fills itself: the next number, a slug made from `title`.
- A command that renames a file and rewrites the links that point at it.
