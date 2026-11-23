---
type: concept
title: Relation
summary: A property whose shape is `reference` - a typed, directed link from one entity to another, stored as a relative path on the source side only.
spec_section: "§9–11"
related:
  - "[Entity](entity.md)"
  - "[Schema](schema.md)"
  - "[Reference resolution](reference-resolution.md)"
---
# Relation

```
transcript ── derived_from ──▶ script
```

A relation is a property of the **source** type whose shape is `reference`, with a `target` type:

```yaml
properties:
  derived_from: { type: reference, target: script }
  recording_of: { type: reference, target: [episode, meeting] }   # either type
  sources:
    type: list
    required: true                                                # at least one
    items: { type: reference, target: script }
  speakers:
    type: list
    items:
      type: object
      fields:
        person: { type: reference, target: person }               # nested
```

- **Anywhere a shape can go**: top-level, list `items`, map `values`, or an object field. Problems name the full path, e.g. `speakers[1].person`.
- **One or several targets.** With `target: [episode, meeting]`, an entity of either type passes.
- **Only declared keys are relations.** An undeclared key that happens to look like a path is ordinary metadata. There is no global relation registry.

## Cardinality

`type: reference` holds exactly one reference. For several, declare a `list` of references:

```yaml
derived_from: "[Episode 42 script](../scripts/episode-42.md)"  # reference: one
sources:                                                        # list of reference
  - ../scripts/episode-42.md
  - "[Notes](<../notes/my notes.md>)"
```

| Value | `reference` | `list` of `reference` |
|---|---|---|
| `null`, `""` | absent | absent |
| `[]` | `relation-invalid-value` | absent |
| one reference | checked | `relation-invalid-value`: write a one-item list |
| a list | `relation-invalid-value`: declare `type: list` | each item checked; an empty item is `relation-invalid-value` |

A `required: true` reference that is absent is `relation-missing`. On a list, `required: true` means "at least one". See [decision 0010](../decisions/0010-concept-files-and-reference-properties.md).

## Source side only

The target never stores the inverse. A script does not list its transcripts. This avoids duplicated state that drifts out of sync. Reverse navigation comes from tools (Obsidian backlinks) or a future derived index.

How each reference is checked: [reference resolution](reference-resolution.md).

## Relation definitions (reserved)

A later version will let a reference name a shared **relation definition**, a file in `.knott/relations/` that says what a link means (its inverse name, whether it may form a cycle). The format is agreed in [decision 0010](../decisions/0010-concept-files-and-reference-properties.md), but nothing reads it yet, so both names are reserved:

- a `relation:` key on a reference is `schema-invalid-field`
- a `.knott/relations/` folder is `schema-invalid-field`

`target` will stay on the property, so a concept file will still list every key its entities may have.
