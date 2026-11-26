---
type: intent
title: Read the vault as data
status: open
raised_on: 2026-11-26
github_issue: 9
concepts:
  - "[Entity](../concepts/entity.md)"
  - "[Attribute](../concepts/attribute.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
---
# Read the vault as data

## Need

Knott can say whether a vault is valid, what its types are and who links to one entity. It cannot answer a question about the entities themselves. An agent that needs "every draft spec" or "what does this decision link to" falls back on `grep` and on reading whole files, and so re-implements what knott already knows:

- **Types.** `grep "type: concept"` misses the subtypes of `concept`.
- **Values.** `grep "status: draft"` misses `status: "draft"`, matches the same words in a body, and cannot look inside a list.
- **Links.** A reference is a path relative to the file that holds it, or a `kid`. Following one means resolving it by hand; following five means five file reads to learn each target's type.
- **Cost.** Reading a file to learn three frontmatter values also pays for its whole body.

Applications built on a vault (a practice app, a scheduler, a dashboard) have the same need and would each parse frontmatter slightly differently from `knott validate`.

## Example

In this folder:

- "Which specs are not released yet?" is one command that returns paths and titles, not fourteen file reads.
- "What is spec 0006 connected to?" is one command that returns its properties, each outgoing reference with the target's path and type, and the incoming links that `knott refs` shows, without the 200-line body.
- "Which decisions affect the Relation concept?" is a filter on a reference property by its target, whatever relative path each decision wrote.

## Open questions

Listing and showing entities are answered by [spec 0016](../specs/0016-list-and-show-entities.md), and one type's details from `knott types NAME` by [spec 0017](../specs/0017-types-for-one-type.md). Left for later specs:

- An export of the whole vault as one versioned JSON document, with the validation result attached.
- A content fingerprint per entity, so a consumer can sync only what changed.
- Following chains of links: a neighbourhood to depth N, a path between two entities, entities nobody references.
- Filters beyond equality: comparisons on dates and numbers, "or", filters on nested fields.
