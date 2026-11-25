---
type: intent
title: Concept inheritance
status: open
raised_on: 2026-11-25
github_issue: 17
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Ontology](../concepts/ontology.md)"
---
# Concept inheritance

## Need

Real ontologies have "is a" structure: a tool, a person and an organization are all kinds of concept. Knott's types are flat, so an author has two bad options:

- **Separate types.** Shared properties (`aliases`, `status`, `created`) are copied into every concept file, and a reference that may point at "any concept" lists each type: `target: [concept, tool, person, organization]`. `knott view` draws one edge per source and target pair, and the diagram becomes too dense to read.
- **One type with a `kind` enum.** The diagram is clean, but properties that only one kind has (`homepage`, `made_by`) become optional on everything, and a reference can no longer say "must be a person".

A second need is the same problem seen from a reference: a set of types named once and used as a target (the "group" of [issue #18](https://github.com/nesterione/knott/issues/18)).

## Example

A knowledge-base vault with 9 types and 10 relations produced about 40 edges in `knott view`. With `tool`, `person` and `organization` declared as kinds of `concept`, the shared properties are written once, `target: concept` accepts all four, `target: person` still accepts only a person, and the diagram has about 12 edges.

The same vault wants `related` to accept `concept`, `source` or `synthesis`. An abstract type `page` that the three extend is that group: it is declared once, has no entities of its own, and `target: page` draws one edge.

## Open questions

Answered by [spec 0013](../specs/0013-concept-inheritance.md). Left for a later spec:

- A child that redefines an inherited property (narrows an enum, makes it required).
- A type in two families at once: several parents, or a group that is not a parent.
