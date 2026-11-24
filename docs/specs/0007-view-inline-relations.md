---
type: spec
title: "0007: The view's Relations panel lists inline relations"
status: accepted
created_on: 2026-11-24
decisions:
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
concepts:
  - "[Relation](../concepts/relation.md)"
  - "[Ontology](../concepts/ontology.md)"
amends:
  - "[0006](0006-relation-definitions.md)"
---
# 0007: The view's Relations panel lists inline relations

## Summary

The Relations panel of `knott view` listed only relation files. It now lists every link in the vault in two sections: **Defined** (relation files, each with the properties that name it) and **Inline** (reference properties that name no relation file), grouped by what they point at. Several inline relations with the same target are the candidates for a shared relation file, and the panel now shows them together. Only `knott view` changes.

## Behaviour

An **inline relation** is a reference property whose `OntologyAttribute.relation` is `None`: it names no relation, or a name no relation file defines ([`relation-unknown`](../issues/relation-unknown.md)). Its identity is `<type>.<property path>`.

### The button

- The header button reads `Relations (N defined · M inline)`. A part whose count is 0 is left out: `Relations (7 inline)`, `Relations (4 defined)`.
- `N` is the number of relation files. `M` is the number of inline relations: one per property, whatever the number of its targets.
- The button is hidden only when both counts are 0. A vault without relation files now has the button when it has references.

### The panel

The line under the title repeats the counts: `4 defined · 7 inline`. A section with nothing to list is left out.

**Defined** lists every relation file, sorted by name, as in spec 0006, with two changes:

- The guidance is folded under a "When to use it" toggle, closed at first. It is still shown verbatim and HTML-escaped.
- Under each relation, one row per property that names it: `<type>.<property path>`, then `→` and its targets, then the required mark. Rows are ordered by type, then schema order. A relation no property names says "No property uses it".

**Inline** lists the inline relations in groups, one group per distinct set of targets:

- A group is headed `→ <targets>`, followed by `· N properties` when it holds more than one.
- Groups are ordered by size, largest first, then by heading.
- Each row is `<type>.<property path>` with the required mark, ordered by type, then schema order.

In both sections, targets are written as in the property table: known targets joined by ` | `, each linking to its type; a target no concept defines is marked `(unknown)`. A type name in a row links to that type's panel.

### Embedded data

The page data gains `reference_properties`: a list of `{type, path, relation, targets, unknown_targets, required}`, one per reference property at any depth, ordered by type, then schema order. `relation` is `None` for an inline relation. `required` follows the rule of edges: every step on the path is required.

### Python API

`knott.view.reference_properties(ontology) -> list[dict]` returns that list.

## Edge cases

| Case | Result |
|---|---|
| A property with `target: [episode, meeting]` | one inline row, in the group `→ episode \| meeting`; it is still two edges in the graph |
| A property whose only target no concept defines | listed, in the group `→ x (unknown)`; it has no edge |
| `relation: nowhere` with no such file | inline; `knott validate` reports `relation-unknown` |
| A relation file no property names | listed under Defined with "No property uses it" |
| A vault with relation files and no inline relations | no Inline section; the button reads `Relations (N defined)` |
| A vault with no reference properties and no relation files | the button stays hidden |

## Out of scope

- Drawing inline and defined relations differently in the graph.
- Suggesting a relation name for a group of inline relations.
- Listing inline relations in `knott types --verbose`; its property table already shows which references name a relation.

## Compatibility

Additive. The page data gains one key; `relations`, `edges` and `referenced_by` are unchanged. The button's label changes from `Relations (N)`, and guidance in the panel is now one click away.
