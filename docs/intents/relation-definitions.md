---
type: intent
title: Relation definitions
status: open
raised_on: 2026-11-23
concepts:
  - "[Relation](../concepts/relation.md)"
  - "[Ontology](../concepts/ontology.md)"
---
# Relation definitions

## Need

A reference property says where a link points, but not what the link *means* beyond its key name. The same link is declared again in every concept that uses it, under different keys (`affects` on decisions and `about` on issue codes both mean "this is about that concept"), with the description copied each time. Nothing can be said about the link itself: what it is called when read from the target side, that it goes both ways, or that following it must never lead back to the start. Without that, the target side of a link has no name, reverse lookup can only list raw property paths, and a loop of `supersedes` links passes validation.

## Example

The docs vault:

- `decision.supersedes → decision` must never form a loop: 0012 supersedes 0011, which supersedes 0012, is a mistake that should be reported.
- `concept.related → concept` goes both ways: if Entity lists Schema as related, Schema's page should show Entity as related too, without editing Schema.
- `decision.affects` and `issue_code.about` both mean "about this concept". Seen from a concept, both should be listed as one group, "discussed in".

## Open questions

Answered by [spec 0006](../specs/0006-relation-definitions.md).
