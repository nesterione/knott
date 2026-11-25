---
type: intent
title: Enumerated values
status: open
raised_on: 2026-10-19
github_issue: 4
concepts:
  - "[Attribute](../concepts/attribute.md)"
  - "[Schema](../concepts/schema.md)"
---
# Enumerated values

## Need

Many properties only make sense with a small fixed set of values: grammatical gender, part of speech, CEFR level, an exercise kind, a review status. Today they are plain strings, so a typo or a synonym is accepted, and tools that read the vault then treat the entity as having no value at all. An agent that writes the entity has nowhere to look up which values are allowed.

## Example

A language-learning vault writes gender as `m` or `f`. An agent creates a `lexeme` draft with `gender: female`, and `knott validate` passes. With the set declared in the concept, validation reports the value and lists the allowed ones, and `knott types --verbose` shows the set before the agent writes the file. The same holds for `level` (`A1` to `C2`, each with a line saying what it means) and for a list such as `tags`, where every item must come from the set.

## Open questions

Answered by [spec 0009](../specs/0009-enum-properties.md). Left for a later spec:

- Whether a set can be defined once and used by several types, such as `level` on lexemes, topics and lessons.
