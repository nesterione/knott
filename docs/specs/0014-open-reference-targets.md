---
type: spec
title: "0014: Open reference targets"
status: draft
created_on: 2026-11-25
realizes:
  - "[Open reference targets](../intents/open-reference-targets.md)"
decisions:
  - "[0004](../decisions/0004-strict-typing.md)"
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
concepts:
  - "[Relation](../concepts/relation.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Ontology](../concepts/ontology.md)"
  - "[Loop](../concepts/loop.md)"
amends:
  - "[0005](0005-concept-files.md)"
  - "[0006](0006-relation-definitions.md)"
  - "[0007](0007-view-inline-relations.md)"
  - "[0010](0010-loops.md)"
---
# 0014: Open reference targets

## Summary

A reference can be declared `target: any`: its value may be any entity in the vault, of any type. `knott view` draws no edge for such a reference and marks the type that declares it. `target` stays required, so an open reference is always written on purpose. The name `any` can no longer be a type. Named groups of types are not added: an abstract parent ([0013](0013-concept-inheritance.md)) is the group. This spec does not depend on 0013 and can be implemented first; the two rules that mention inheritance apply once both are in.

## Behaviour

### `target: any`

```yaml
properties:
  related:
    type: list
    items: { type: reference, relation: related, target: any }
  promoted_to: { type: reference, target: any }
```

- `any` is written alone, as a string. In a list (`[any]`, `[any, episode]`) it is `schema-invalid-field` at the line of `target`; the names beside it are kept and enforced, and a list left empty skips the type check, as with unknown targets.
- `target` is still required on a `reference`. A missing target does not mean `any`.
- `any` is a reserved name. A concept file with `name: any` is `schema-invalid-field` at the line of `name`, and defines no type.

### Validation

A value of an open reference goes through every step of reference resolution except the last:

```
value is a path or kid in a valid form            → relation-invalid-value
resolved path stays inside the vault root         → relation-target-outside-vault
target exists, with exact case matching           → relation-target-not-found
target is a Knott entity                          → relation-target-not-entity
(no type check)
```

- The target must have a frontmatter `type`. A type no concept defines still passes: that entity has its own `entity-unknown-type`.
- `relation-target-type-mismatch` is never reported for an open reference.
- Cardinality, `required` and nesting work as for any reference.

### Relation and loop checks

An open reference **can target every concept**. So:

- `relation-symmetric-mismatch` is never reported for it.
- `relation-inverse-conflict`: when a property naming the relation is open, the `inverse` must not equal a top-level property of any concept in the vault.
- A loop's inverse need `<inverse>: <type>` ([0010](0010-loops.md)) is valid when a property of that type names the relation and is open, whatever the loop's type.
- `relation-cycle`, reverse lookup and `knott refs` are unchanged.

## CLI and API

### `knott types --verbose`

The target is printed as written:

```
    related      list of reference → any  (related)  Anything worth reading next.
    promoted_to  reference → any
```

### `knott view`

- **No edge** is drawn for an open reference.
- **The type's box** carries one mark, `→ any`, followed by `×N` when the type declares more than one. Its tooltip lists them: `related[] (related)`, `promoted_to`. A type that only inherits an open reference has no mark; its ancestor has it.
- **A header toggle**, `Open references (N)`, hidden when the vault has none. On, every type with a mark is highlighted and the others dim, so "what is open" can be read at a glance. It is off at first and not remembered.
- **The type's panel**, in the property table and under *References out*: `→ any`.
- ***Referenced by*** in every type's panel ends with a group `from anywhere`, folded at first, with one row per open reference in the vault: `<type>.<property path>` and its relation. Its rows are not counted with the others.
- **The Relations panel**: a row of a defined relation reads `<type>.<property path> → any`. Inline open references form one group headed `→ any`, ordered with the other groups by size.

**Embedded data.** A reference attribute and a `reference_properties` row gain `open` (boolean); `targets` and `unknown_targets` are empty when it is `true`. `edges` has no entry for it. `referenced_by` is unchanged: the page builds the `from anywhere` group from `reference_properties`.

### Python API

`OntologyAttribute.open: bool = False`. `targets` is `[]` for an open reference.

### Agent skill and guide

To add to the bundled skill when this is implemented:

- `→ any` in `knott types --verbose` means the value can be any entity. It must still be an existing entity file in the vault: a plain note, a URL or a file outside the vault is an error.
- Read the property's description or its relation's guidance to decide what belongs there. Open is not "optional" and not "anything loosely connected".
- When writing a concept file:
  - Use `target: any` only for a link that is open by nature ("see also", "promoted to"). If the types can be named, name them or target their parent.
  - Never change a target to `any` to make `relation-target-type-mismatch` go away; fix the reference.
  - Describe what belongs in an open property: with no target type, the description is the only guidance.

To add to *Writing schemas*:

- **Use `any` only for a link that is open by nature**: "see also", "promoted to", "created by". If you can name the types, name them, or target their parent.
- **Prefer a parent over `any` when the set is a family.** `target: page` checks the type and draws one edge; `any` checks only that the value is an entity.
- **Say what belongs there in the description.** With no target type, the description is the only guidance an agent has.
- **Give an open link a relation file**, so `knott refs` shows it under a name from the target side.
- **Keep them few.** A vault where most references are open has lost its type checks.

## Edge cases

| Case | Result |
|---|---|
| `target: any`, value points at a note with no frontmatter | `relation-target-not-entity` |
| `target: any`, value points at an entity whose type no concept defines | valid here; the target has `entity-unknown-type` |
| `target: any`, value points at an entity of an abstract type | valid here; the target has `entity-abstract-type` |
| `target: [any, episode]` | `schema-invalid-field`; the property accepts `episode` only |
| `target: [any]` | `schema-invalid-field`; no target is left, so any entity type passes |
| `target: Any` or `target: "*"` | `schema-unknown-target`, as for any name no concept defines |
| A concept file with `name: any` | `schema-invalid-field`; its entities are `entity-unknown-type` |
| A relation with `inverse: notes`, named by an open property, and some concept has a `notes` property | `relation-inverse-conflict` naming that concept |
| A symmetric relation on an open property | valid |

## Out of scope

- Named groups of types (`wiki = [concept, source, synthesis]`). An abstract parent covers a family; types that share nothing are listed.
- A missing `target` meaning `any`.
- "Any entity except…" and other target expressions.
- Drawing open references as edges to a shared node.

## Compatibility

Additive, with one exception: a vault that has a type named `any` must rename it. Before this change `target: any` in a vault without such a type was `schema-unknown-target` and skipped the type check, so values that passed still pass. Ontology API and view data additions only. Minor version.
