---
type: spec
title: "0013: Concept inheritance"
status: implemented
created_on: 2026-11-25
released_in: "0.12.0"
realizes:
  - "[Concept inheritance](../intents/concept-inheritance.md)"
decisions:
  - "[0003](../decisions/0003-source-side-relations.md)"
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Entity](../concepts/entity.md)"
  - "[Ontology](../concepts/ontology.md)"
  - "[Loop](../concepts/loop.md)"
amends:
  - "[0005](0005-concept-files.md)"
  - "[0006](0006-relation-definitions.md)"
  - "[0007](0007-view-inline-relations.md)"
  - "[0010](0010-loops.md)"
  - "[0011](0011-entity-location.md)"
  - "[0012](0012-entity-file-names.md)"
---
# 0013: Concept inheritance

## Summary

A concept can declare a parent with `extends`. The child inherits the parent's properties, template, `path` and `kid: required`, and adds its own properties. A reference that targets a type accepts entities of that type and of every type below it. A concept marked `abstract: true` cannot be an entity's `type`: it exists to share properties and to be a target, which also makes it the way to name a group of types. `knott view` draws a reference once, at the type that declares it, and shows "is a" as its own kind of edge. A vault that uses neither key behaves as before.

## Behaviour

### `extends` and `abstract`

```yaml
# .knott/concepts/concept.md
---
name: concept
abstract: true
properties:
  title: { type: string, required: true }
  related:
    type: list
    items: { type: reference, target: concept }
---
```

```yaml
# .knott/concepts/tool.md
---
name: tool
extends: concept
properties:
  homepage: { type: string }
  made_by:  { type: reference, target: organization }
---
```

- `extends` is a top-level key: the `name` of one other concept. A concept has at most one parent. Any depth is allowed.
- `abstract` is a top-level key: `true` or `false`, default `false`. It is not inherited: a child of an abstract concept is concrete unless it says `abstract: true` itself. An abstract concept may have no children.
- **Terms.** The *ancestors* of a type are its parent, the parent's parent, and so on. The *subtypes* of a type are every type that has it as an ancestor. Type `A` **is-a** `B` when `A` is `B` or `B` is an ancestor of `A`. The rules below use the term in this sense.
- An entity writes its own type: `type: tool`. Nothing in the entity names the parent.

### What a child inherits

| From the parent | Rule |
|---|---|
| `properties` | All of them, with every key (`required`, `description`, `relation`, …). The child's effective properties are the inherited ones, root ancestor first, then its own, each in schema order. |
| body template | Inherited when the child's body is empty. A child with a body uses its own, whole; the two are never merged. |
| `path` | Inherited when the child declares none. A child's own `path` replaces it. |
| `kid: required` | Inherited. A child cannot turn it off. |
| `description`, `abstract` | Not inherited. |

A child can only **add** properties. A property whose name an ancestor already declares is `schema-property-redefined`: the child's definition is dropped and the inherited one stands. Two children of one parent may each declare a property with the same name; they are unrelated.

The `filename` key of [0012](0012-entity-file-names.md) follows the rule of `path`.

### Checks on `extends` and `abstract`

- A value of `extends` that is not a string, or of `abstract` that is not a boolean, is `schema-invalid-field`. The concept loads without the key. An empty `extends:` or `abstract:` is the same as no key.
- `extends` names no concept: `schema-unknown-parent`. The concept loads without a parent.
- `extends` forms a cycle, a concept that extends itself included: `schema-extends-cycle`, one issue per concept in the cycle. Each of them loads without a parent. A concept below a cycle keeps its chain up to the first concept in it.
- A parent whose file has errors and did not load counts as unknown.

### References accept subtypes

A reference with target `T` accepts an entity whose type is-a `T`. With a list, it is enough that the type is-a one of the listed types.

- `target: concept` accepts `concept`, `tool`, `person`. `target: tool` accepts `tool` and its subtypes, not `concept`.
- An abstract type is a valid target. So is a type listed next to its own ancestor (`target: [concept, tool]`), though the second name adds nothing.
- The message of `relation-target-type-mismatch` is unchanged; it names the declared targets.
- This is the meaning of "can target" everywhere below.

### Entities of an abstract type

An entity whose `type` is an abstract concept is `entity-abstract-type`. Its properties are still checked against that concept, and references to it resolve and pass the type check as for any entity of that type.

### Issues on inherited properties

An issue on an inherited property is reported on the entity as before. Its message ends with a line that names the declaring file:

```
✗ tools/ripgrep.md:1
  required attribute `title` (string) is missing or empty
  declared in .knott/concepts/concept.md (`tool` extends `concept`)
```

For a farther ancestor the line names the parent in between: ``(`cli` extends `concept` through `tool`)``.

### Relation checks ([0006](0006-relation-definitions.md))

- `relation-inverse-conflict`: the `inverse` must not equal a top-level property, own or inherited, of any concept the naming property can target, subtypes included. It is reported once per conflicting concept that *declares* the property; when that concept is not itself a target, the message says the property is inherited by one.
- `relation-symmetric-mismatch`: the property's own concept is-a at least one of its targets, or the issue is reported. An inherited property is checked once, at the concept that declares it.
- `relation-cycle` and reverse lookup work on resolved references and do not change. `knott refs` is unchanged.

### Loops ([0010](0010-loops.md))

- A loop with `type: T` follows every entity whose type is-a `T`. Its `property` and property needs may be inherited properties of `T`.
- An inverse need `<inverse>: U` is met, for each listed type `U`, by an entity whose type is-a `U`. The check that some property naming the relation can target the loop's type uses "can target" as defined above.
- Two loops follow the same thing, and are `schema-duplicate-loop`, when they name the same `property` and the type of one is-a the type of the other.
- A loop on an abstract type is valid.
- `loop-invalid-target` conditions that say "a top-level property of the type" include inherited properties.
- `knott loops` lists subtype entities under the parent's loop like any other; the text output is unchanged. In `--format json` and the Python API, `LoopEntity` gains `type`, the entity's own type.
- `knott types --verbose` prints a loop as `<type>.<property>` with the type the loop file names.

## Issue codes

| Code | Stage | When | `field` / `line` |
|---|---|---|---|
| `schema-unknown-parent` | schema | `extends` names a type no concept file defines; the message lists the known types | `extends` / that line |
| `schema-extends-cycle` | schema | the concept is part of an `extends` cycle; the message shows the cycle (`a → b → a`) | `extends` / that line |
| `schema-property-redefined` | schema | a concept declares a property an ancestor already declares; the message names the ancestor and its file | `properties.<name>` / the line of the child's property |
| `entity-abstract-type` | entity | an entity's `type` is an abstract concept; the message lists its concrete subtypes | `type` / the line of `type` |

```
✗ concepts/zettelkasten.md:2
  `concept` is abstract and cannot be an entity's type; use `organization`, `person` or `tool`
```

The message lists the concrete subtypes at any depth, sorted by name. With none, it ends after "type".

## CLI and API

### `knott types`

Plain output is unchanged. `--verbose` adds lines and splits the properties by where they are declared:

```
concept  (.knott/concepts/concept.md)
  A named idea in the knowledge base.
  abstract: yes
  subtypes: organization, person, tool
  template: yes
  …

tool  (.knott/concepts/tool.md)
  A piece of software.
  extends: concept
  kid: required (from concept)
  template: yes (from concept)
  path: concepts/** (from concept)
  references: related[], made_by
  properties (from concept):
    title*   string
    related  list of reference → concept
  properties:
    homepage  string
    made_by   reference → organization
```

- `extends: <parent>`, then `abstract: yes`, then `subtypes:` come first, after the description; the existing lines keep their order. `subtypes:` lists the direct children, sorted; it is left out when there are none.
- `(from <type>)` marks an inherited template, `path` or `kid: required`, naming the type that declares it.
- One `properties (from <type>):` block per ancestor that declares properties, root first, then `properties:` for the type's own. `references:` lists inherited and own references, in that order.

### `knott view`

**In the diagram**

- **A reference is drawn once**, from the type that declares it to each declared target. A child draws no edge for a reference it inherits, and a target's subtypes get no edge of their own.
- **"Is a" is its own edge**: from child to parent, thin, grey, solid, with a hollow triangle at the parent and no label. It never counts as a reference.
- **In the Layered layout** a child sits in the layer below its parent, with its siblings next to it, so a family reads as a tree.
- **An abstract type** has a dashed border and its name in italics. It shows `abstract` where the entity count would be.
- **Hovering a type** highlights its own edges, its "is a" edges, and the edges of its ancestors: the references it inherits and the references that can point at it through an ancestor.
- **Folding.** A type with subtypes has a `▾ N` mark (N subtypes). Clicking it hides the subtypes and shows `▸ N`. While they are hidden:
  - an edge to or from a hidden type is drawn at the folded ancestor;
  - edges that then share source, target and label are drawn once, required if any of them is;
  - an edge that would now start and end at the folded type is drawn as a self-reference.

  A header button, `Fold subtypes` / `Unfold subtypes`, applies to every family. It reads `Unfold subtypes` when no type on screen still shows its subtypes. It is hidden when no type has a parent. `N` in the mark counts subtypes at any depth. The page starts unfolded and remembers the folded types per vault, in the browser, as it remembers the layout.

**In a type's panel**

- Under the name: `extends <parent>` and `subtypes: …`, each a link to that type, and `abstract` when it is.
- The property table marks an inherited row with `from <type>`.
- **References out** lists inherited and own references.
- **Referenced by** lists every reference property that can target the type. A row that reaches it through an ancestor ends with `via <ancestor>`.
- The entity count is followed by `N with subtypes` when the type has subtypes.
- **Loops** lists the loops of the type and of its ancestors; an inherited one is marked `from <type>`. On the Loops board a card of a subtype entity shows its type after the path.

**Embedded data**

- Each type gains `extends` (name or `None`), `abstract`, `ancestors` (parent first), `subtypes` (direct children), `inherited` and `count_with_subtypes`.
- Each top-level attribute gains `inherited_from` (type name or `None`).
- `edges` holds each reference once, at its declaring type. A new list `inheritance` holds `{child, parent}`.
- `reference_properties` holds each property once, at its declaring type. A `referenced_by` row gains `via` (ancestor name or `None`).

### Python API

- `OntologyType.extends: str | None`, `abstract: bool`, `ancestors: list[str]`, `subtypes: list[str]`.
- `OntologyType.properties` is the effective list. `OntologyAttribute.inherited_from: str | None` is set on inherited top-level properties.
- `OntologyType.template`, `entity_paths`, `filename` and `kid_required` are the effective values. `count` is the type's own entities.
- `OntologyType.inherited: dict[str, str]` says which ancestor an inherited setting comes from, by key: `template`, `path`, `filename`, `kid`. A key is absent when the type declares the setting itself or has none. `knott types --verbose` prints `(from <type>)` from it, on the `filename:` line too.

### Agent skill and guide

To add to the bundled skill when this is implemented:

- An entity's `type` is always a concrete type. When a reference wants `concept` and `knott types --verbose` shows `abstract: yes`, create or pick an entity of one of its `subtypes`.
- Pick the most specific type that fits: a `tool`, not a `concept`, when the entity is a tool.
- Fill the properties in the `properties (from …)` blocks too; they are required or optional exactly as marked there.
- Take the template and folder from the lines marked `(from <type>)` as if the type declared them.
- Never write `extends` or the parent's name in an entity.
- `entity-abstract-type`: change `type` to the subtype the message lists that fits. Never remove `abstract` from the concept to make an entity pass.
- When writing a concept file:
  - `extends` is for a real "is a": the child shares the parent's properties and is accepted wherever the parent is. Kinds with the same properties are a `kind` enum, not subtypes.
  - A child only adds properties. Never repeat an inherited one (`schema-property-redefined`); if a child needs it different, the property belongs on the children, not the parent.
  - To let a reference accept a set of types, give them an abstract parent and target it, rather than repeating a list on every property.
  - Target the narrowest type that is true; target the parent only when any kind is right.

To add to *Writing schemas*, replacing the "Several possible types?" item (the skill carries the short form above, the guide the full list):

- **Use `extends` for a real "is a"**: the child is a kind of the parent, shares its properties, and should be accepted wherever the parent is. If you would not say "a tool is a concept", it is not a subtype.
- **Use a `kind` enum instead** when the kinds have the same properties and no reference needs "only this kind".
- **Don't add a parent only to thin the diagram.** A parent with no shared properties and no reference that targets it is noise.
- **Make the parent `abstract`** when nothing is "just a concept". Leave it concrete when such entities exist.
- **Name a group of types with an abstract parent.** `page` extended by `concept`, `source` and `synthesis` is declared once, and `target: page` replaces the list on every property.
- **Target the narrowest type that is true**: `made_by → organization`, not `→ concept`. Target the parent only when any kind is right.
- **Put a property on the highest type where every subtype has it**, and nowhere else. A property that half the children leave empty belongs on those children.
- **Keep the tree shallow.** Two levels cover most vaults; a child cannot change what it inherits.
- **List targets (`[episode, meeting]`) for types that share nothing**, rather than inventing a parent for them.

## Edge cases

| Case | Result |
|---|---|
| `tool` extends `concept`; `related: {target: concept}` points at a tool | valid |
| `made_by: {target: tool}` points at a plain `concept` entity | `relation-target-type-mismatch` |
| `tool` declares `title`, which `concept` declares | `schema-property-redefined` on `tool`; `tool` keeps the inherited `title` |
| `concept` gains a property that `tool` already has | the same issue, on `tool` |
| `tool` and `person` both declare `homepage` | valid |
| `a` extends `b`, `b` extends `a`, `c` extends `a` | `schema-extends-cycle` on `a` and `b`; `c` extends `a`, which has no parent |
| `extends: concpt` | `schema-unknown-parent`; `tool` loads as a root type, so its entities are not accepted by `target: concept` |
| Entity with `type: concept`, `concept` abstract | `entity-abstract-type`; its properties are still checked |
| Parent has a template, child's body is only whitespace | the child inherits the template |
| Parent `path: concepts`, child `path: tools` | a tool in `concepts/` is `entity-misplaced` |
| Parent `kid: required`, child says nothing | the child's entities need a `kid` |
| A loop on `concept` over `status`, another on `tool` over `status` | `schema-duplicate-loop` at the second file |
| A symmetric `related` declared on `tool` with `target: concept` | valid: a tool is a concept |
| A symmetric `related` declared on `concept` with `target: tool` | `relation-symmetric-mismatch`: a concept is not a tool |

## Out of scope

- Redefining an inherited property: narrowing an enum, making it required, changing a description. Allowing it later is additive.
- Several parents, and groups that are not parents. A type that belongs to two families lists the targets.
- Dropping the parent's template without providing one.
- `knott refs` output that shows the ancestor a reference came through.
- A check that an abstract type has at least one concrete subtype.

## Compatibility

Additive. `extends` and `abstract` were `schema-invalid-field` before. A vault without them validates and draws exactly as today. Adding `extends` to an existing concept can make its entities invalid (inherited required properties, `path`, `kid: required`); `knott validate` lists them. Ontology API and view data additions only. The message of `schema-duplicate-loop` has a second form, for two loops on a type and its subtype. Version 0.12.0.
