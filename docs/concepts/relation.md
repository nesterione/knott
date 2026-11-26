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
- **Or any entity.** `target: any` makes the reference [open](#open-references): the type is not checked.
- **Only declared keys are relations.** An undeclared key that happens to look like a path is ordinary metadata, even when its name matches a relation definition.

## Open references

Some links are open by nature: "see also", "promoted to", "created by". Declare them with `target: any`:

```yaml
properties:
  related:
    type: list
    items: { type: reference, relation: related, target: any }
```

- **Any entity passes**, of any type. The value must still resolve to an entity in the vault: a plain note, a missing file or a URL is an error as for every reference. Only [`relation-target-type-mismatch`](../issues/relation-target-type-mismatch.md) is never reported.
- **`any` stands alone.** `target: [any, episode]` is `schema-invalid-field`. `target` is still required; leaving it out does not mean `any`.
- **In `knott view`** an open reference has no edge. The type that declares it carries a `→ any` mark, and every type's panel lists the vault's open references under "from anywhere".
- **Prefer a parent when the set is a family.** `target: page`, with `page` an [abstract parent](schema.md#inheritance), checks the type and draws one edge.

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

The target never stores the inverse. A script does not list its transcripts. This avoids duplicated state that drifts out of sync. To read links from the target side, run [`knott refs`](../commands/refs.md) on it, or use Obsidian backlinks.

How each reference is checked: [reference resolution](reference-resolution.md).

## Relation definitions

A **relation definition** says what a link means, once, for every property that uses it. It is a Markdown file in `.knott/relations/`, discovered like concept files (subfolders are only for organisation). The frontmatter is the definition; the body is optional usage guidance, shown by `knott types --verbose` and `knott view`:

```markdown
---
name: supersedes
inverse: superseded_by
acyclic: true
description: This entity replaces the target entirely. The target is kept unchanged as history.
---
Use `supersedes` when the old record is no longer the current answer. When only part of it changes, use `amends`.
```

| Key | Required | Value |
|---|---|---|
| `name` | yes | `^[a-z][a-z0-9_-]*$`; relation and concept names don't clash |
| `description` | no | string |
| `inverse` | no | the link's name read from the target side, same pattern as `name` |
| `symmetric` | no | `true`/`false`, default `false`: the link reads the same both ways |
| `acyclic` | no | `true`/`false`, default `false`: following the links must never lead back |

A reference property opts in with `relation:`, on the `reference` shape itself (for a list, on its `items`). Write it on one line, straight after `type`, so a defined link is easy to tell from a plain one:

```yaml
properties:
  supersedes: { type: reference, relation: supersedes, target: decision }   # defined
  affects:
    type: list
    items: { type: reference, relation: about, target: concept }            # defined
  notes_on:   { type: reference, target: concept }                          # plain
```

- **A plain reference is an inline relation.** It has no file and no shared meaning: its identity is `<type>.<property path>`, which is how `knott refs` labels it (`← guide.concepts[]`). Give it a relation file when a second property means the same thing, or when it needs an `inverse`, `symmetric` or `acyclic`. Those three live only on a definition, never on one property.
- **The property keeps its own `target`.** A relation declares no source or target types and never adds a key to a concept, so a concept file still lists every key its entities may have.
- **Shared.** Many properties may name one relation, in one concept or across concepts, under any key names. `knott refs` groups them together under the `inverse` (here `superseded_by`, `discussed_in`).
- **`inverse` is a read-side label.** `superseded_by` names the link when `knott refs` reads it from the target. It is not a property and not a second relation, and it is never written on the target.
- **Symmetric links need one side.** For `related` (`symmetric: true`), `knott refs` shows the link from both sides; storing it on both is valid but adds nothing. The property's targets must include its own concept, or a concept it [extends](schema.md#inheritance), so the link can point back.
- **Acyclic relations are checked for cycles** across the whole vault, every property that names the relation counting as one graph: [`relation-cycle`](../issues/relation-cycle.md).
- **Unknown names still work.** A `relation:` no file defines is [`relation-unknown`](../issues/relation-unknown.md), and the reference stays a plain one.

Problems with the definitions themselves: [`schema-duplicate-relation`](../issues/schema-duplicate-relation.md), [`relation-inverse-conflict`](../issues/relation-inverse-conflict.md), [`relation-symmetric-mismatch`](../issues/relation-symmetric-mismatch.md). `transitive` is reserved and not supported yet. See [spec 0006](../specs/0006-relation-definitions.md).
