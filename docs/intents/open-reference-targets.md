---
type: intent
title: Open reference targets
status: open
raised_on: 2026-11-25
github_issue: 18
concepts:
  - "[Relation](../concepts/relation.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Ontology](../concepts/ontology.md)"
---
# Open reference targets

## Need

Some references are open on purpose: "see also", "promoted to" and "created by this operation" can point at any entity. Today `target` must list every type by name. That has three costs:

- the list is repeated on every such property and must be edited whenever a type is added;
- `knott view` draws one edge per listed type, so one generic property produces a fan of edges that hides the specific ones;
- a reader cannot tell "open on purpose" from "happens to list six types".

## Example

A `related` property on 2 types that targets 6 types added 12 edges to the diagram, and a `promoted_to` property added 6 more. Written `target: any`, both validate as before (the value must still be an entity in the vault), a seventh type needs no edit, and the diagram shows a mark on the two types instead of 18 edges.

## Open questions

Answered by [spec 0014](../specs/0014-open-reference-targets.md). The named group of types that issue #18 also asks for is covered by an abstract parent, see [Concept inheritance](concept-inheritance.md).
