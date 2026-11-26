---
type: intent
title: Type tree
status: open
raised_on: 2026-11-26
concepts:
  - "[Ontology](../concepts/ontology.md)"
  - "[Schema](../concepts/schema.md)"
---
# Type tree

## Need

A person or an agent opening a vault wants its taxonomy on one screen: which types exist, which are kinds of which, how many entities each has and where they live. Today that takes two commands and some assembly:

- `knott types` prints names only, sorted, with no hierarchy.
- `knott types --verbose` has the hierarchy, but as `extends:` and `subtypes:` lines spread over a page per type.
- `knott view` draws "is a" edges among every reference edge; it has no list to scan or to navigate from.

## Example

A vault with an abstract `record` that `decision` and `spec` extend, and a standalone `concept`. One command prints four lines: `record` with its two kinds indented under it, `concept` beside it, each with its entity count and folder. With descriptions switched on, each type also says what it is and which properties it adds to its parent. In `knott view`, the same tree sits beside the diagram and a click on a row selects that type.

## Open questions

Answered by [spec 0015](../specs/0015-type-tree.md).
