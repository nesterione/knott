---
type: spec
title: "0006: Relation definitions and reverse lookup"
status: accepted
created_on: 2026-11-23
realizes:
  - "[Relation definitions](../intents/relation-definitions.md)"
decisions:
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
  - "[0003](../decisions/0003-source-side-relations.md)"
concepts:
  - "[Relation](../concepts/relation.md)"
  - "[Ontology](../concepts/ontology.md)"
  - "[Schema](../concepts/schema.md)"
amends:
  - "[0005](0005-concept-files.md)"
---
# 0006: Relation definitions and reverse lookup

## Summary

A vault can define relations in `.knott/relations/*.md`: what a link means, its name when read from the target side (`inverse`), whether it goes both ways (`symmetric`), and whether it may loop (`acyclic`). A reference property opts in with `relation: <name>`. A new command, `knott refs PATH`, lists who references an entity, grouped by those names. Nothing is ever stored on the target side. The change is additive: it lifts the reservations spec 0005 put on `.knott/relations/` and the `relation:` key.

## Behaviour

### Relation files

```yaml
# .knott/relations/supersedes.md
---
name: supersedes
inverse: superseded_by
acyclic: true
description: This entity replaces the target. The target stays as history.
---
<!-- Use when the old entity is no longer the current answer. For a partial change, use `amends`. -->
```

- Discovered from `.knott/relations/**/*.md`. Subfolders are only for organisation. Other file types are ignored.
- The frontmatter is the definition. The body is optional usage guidance, stored verbatim (`None` when blank) and shown by `types --verbose` and `view`. It is never checked against anything.
- Keys are closed:

  | Key | Required | Value |
  |---|---|---|
  | `name` | yes | `^[a-z][a-z0-9_-]*$`. Relation names and concept names are separate namespaces. |
  | `description` | no | string |
  | `inverse` | no | a name, same pattern as `name` |
  | `symmetric` | no | `true` / `false` (strict spelling, [0004](../decisions/0004-strict-typing.md)), default `false` |
  | `acyclic` | no | `true` / `false`, default `false` |

- `transitive` is reserved: using it is `schema-invalid-field` ("reserved, not supported yet"). Any other key is `schema-invalid-field` with a "did you mean" suggestion.
- A file with no frontmatter, or invalid YAML, is `schema-invalid-yaml`. Two files with the same `name` are `schema-duplicate-relation`, reported at the second file in path order and naming both.
- A relation no property names is valid. It is listed by `types --verbose`.

### Naming a relation from a property

```yaml
# .knott/concepts/decision.md
properties:
  supersedes: { type: reference, target: decision, relation: supersedes }
  affects:
    type: list
    items: { type: reference, target: concept, relation: about }
```

- `relation:` is allowed on a `reference` shape only, at any depth. On a `list` or `map` it is `schema-invalid-field` with "put `relation:` on `items`" (or `values`). Its value must be a string.
- The property keeps its own `target`, `required` and `description`. The relation declares no source or target types and never adds a key to a concept.
- A name no relation file defines is `relation-unknown`, at the `relation:` line. The reference still works as a plain reference.
- Many properties may name one relation, in one concept or across concepts, under any key names.

### Checks on definitions

Run when the vault loads, on every command, after all concept and relation files are read. Only known targets are considered (unknown ones are already `schema-unknown-target`).

| Rule | Code | Reported at |
|---|---|---|
| Two relations declare the same `inverse` | `relation-inverse-conflict` | the second file's `inverse:` line, naming both |
| An `inverse` equals any relation's `name` | `relation-inverse-conflict` | the `inverse:` line |
| An `inverse` equals its own `name` | `relation-inverse-conflict`, message suggests `symmetric: true` | the `inverse:` line |
| An `inverse` equals a top-level property name of a concept that a property naming this relation can target | `relation-inverse-conflict`, naming the concept and property | the `inverse:` line |
| `symmetric: true` with an `inverse` | `relation-symmetric-mismatch` | the `inverse:` line |
| `symmetric: true` with `acyclic: true` (every symmetric link is a two-step loop) | `relation-symmetric-mismatch` | the `acyclic:` line |
| A property names a symmetric relation, but its known targets don't include the property's own concept | `relation-symmetric-mismatch` | the concept file's `relation:` line |

### Cycles

For each relation with `acyclic: true`, knott builds a graph from the whole vault:

- Nodes are entities. Edges are references at properties that name the relation, at any depth, that pass every resolution check ([reference resolution](../concepts/reference-resolution.md)), including the target-type check. Path and `kid:` references count the same.
- Entities with invalid frontmatter or an unknown type contribute no edges. Unresolved references are already reported and add no edge.
- Each strongly connected component with more than one entity, or an entity that references itself, is one `relation-cycle` issue.
- The issue names one concrete loop through the component, starting at its entity with the smallest path: "`supersedes` must not form a cycle: decisions/0011.md → decisions/0012.md → decisions/0011.md". It is reported at the first entity on that loop, in path order, that is in the run's scope, at the line of its reference to the next entity. `field` is that property's full path (`supersedes`, `history[2].replaces`).
- **Scoped runs** (`knott validate PATH...`) report a cycle when at least one of its entities is in scope, as with `kid-duplicate`. The graph is built lazily, once per run, and only when some property names an acyclic relation.

### Reading links from the target side

Reverse lookup collects, for one entity E, every reference in the vault that resolves to E. Only declared reference properties count; an undeclared key that looks like a path never does. A reference that resolves to E but fails the target-type check is still listed, because it still points at E; `validate` reports the mismatch separately.

References are grouped by a **label**:

| The referring property | Group label | Kind |
|---|---|---|
| names a relation with an `inverse` | the inverse, e.g. `superseded_by` | `inverse` |
| names a symmetric relation | the relation's name, e.g. `related` | `symmetric` |
| names a relation without `inverse`, not symmetric | `← <name>`, e.g. `← about` | `relation` |
| names no relation | `← <type>.<path>`, e.g. `← guide.concepts[]` (path notation as in `references()`) | `property` |

- Properties from different concepts that name the same relation share one group. That is how `decision.affects` and `issue_code.about` both appear under `discussed_in`.
- **Symmetric groups also include E's own outgoing references** at properties naming that relation. Each linked entity appears once, with direction `in` (only the other side stores it), `out` (only E stores it) or `both`. Storing a symmetric link on both sides is valid and is never reported.
- Groups are ordered: `inverse`, `symmetric` and `relation` groups by label, then `property` groups by label. Within a group, references are ordered by source path, then field.

## Issue codes

| Code | Stage | When | `field` / `line` |
|---|---|---|---|
| `schema-duplicate-relation` | schema | two relation files share a `name` | `name` / its line in the second file |
| `relation-unknown` | schema | a property names an undefined relation | `properties.<path>.relation` / that line |
| `relation-inverse-conflict` | schema | see *Checks on definitions* | `inverse` / its line |
| `relation-symmetric-mismatch` | schema | see *Checks on definitions* | the offending key / its line |
| `relation-cycle` | relation | an acyclic relation loops | the property path / the reference's line |

`schema-invalid-field` and `schema-invalid-yaml` also cover relation files. No existing code changes meaning. The two reservation messages from spec 0005 (`.knott/relations/` exists; `relation:` used) are removed.

## CLI and API

### `knott refs PATH`

`PATH` is an entity file (relative to the current directory) or `kid:<uuid>`.

```
$ knott refs docs/concepts/relation.md
concepts/relation.md  concept

discussed_in
  decisions/0003-source-side-relations.md   decision    affects[0]
  issues/relation-invalid-value.md          issue_code  about

related
  concepts/entity.md   concept  related[0]  ⇄
  concepts/schema.md   concept  related[1]  ←

← guide.concepts[]
  guides/writing-schemas.md  guide  concepts[2]
```

- Paths are vault-relative. In symmetric groups the last column is the direction: `←` (in), `→` (out), `⇄` (both). An entity nobody references prints its header line and `no references`.
- `--format json`:

  ```json
  {
    "entity": {"path": "concepts/relation.md", "type": "concept", "kid": null},
    "groups": [
      {"label": "discussed_in", "kind": "inverse", "relation": "about",
       "references": [{"path": "decisions/0003-source-side-relations.md", "type": "decision",
                       "kid": null, "field": "affects[0]", "line": 7, "direction": "in"}]}
    ]
  }
  ```

  `relation` is `null` for `property` groups. `direction` is always `in` outside symmetric groups.
- Exit codes: `0` on success, including no references. `1` when the vault has the legacy layout (the `schema-legacy-layout` issue goes to stderr, as for `types` and `view`). `2` when PATH doesn't exist, isn't inside the vault, isn't an entity, or a `kid:` matches no entity or several.
- `refs` does not validate the vault. Schema issues don't stop it; it works with the concepts and relations that loaded.

### `knott types --verbose`

- A property that names a relation shows it after the type: `affects  list of reference → concept  (about)`.
- A `relations:` section after the types lists every relation: name, then `inverse: <x>`, `symmetric`, `acyclic` as they apply, then the description and the guidance.

### `knott view`

- An edge whose property names a relation is labelled with the relation's name instead of the property path.
- The side panel's "Referenced by" list uses the reverse-lookup groups and labels.
- A "Relations" section lists every relation with its keys, description and guidance.

### Python API

- `Knott.refs(path_or_kid: str | Path) -> Refs`. `Refs` has `entity: EntityRef(path, type, kid)` and `groups: list[RefGroup(label, kind, relation, references: list[Ref(path, type, kid, field, line, direction)])]`. Raises `PathNotFoundError` / `KnottError` for the exit-2 cases.
- `Ontology.relations: list[RelationDefinition(name, description, inverse, symmetric, acyclic, guidance, path)]`.
- `OntologyAttribute.relation: str | None` on reference nodes.

## Edge cases

| Case | Result |
|---|---|
| `relation: about` on the `list`, not its `items` | `schema-invalid-field`, "put `relation:` on `items`" |
| A self-reference with an acyclic relation (`a.md` supersedes `a.md`) | `relation-cycle`: "a.md → a.md" |
| Two separate loops of the same relation | two `relation-cycle` issues |
| One loop through two properties naming the same relation | one issue; it's one graph per relation |
| A loop made of edges from two different acyclic relations (a `supersedes` b, b `amends` a) | no issue; each relation is checked on its own |
| A cycle member's reference has the wrong target type | that edge doesn't count; `relation-target-type-mismatch` is reported instead |
| A symmetric relation stored on both sides | valid; shown once with `⇄` |
| A symmetric relation named by a property whose targets are `[concept, guide]`, from `concept` | valid: the targets include the property's own concept |
| `knott refs` on a concept file in `.knott/concepts/` | exit 2: not an entity |
| A relation whose `inverse` equals a nested field name (`speakers[].role`) of a target concept | valid; only top-level property names conflict |
| An `inverse` that equals a property of a concept the relation's properties can't target | valid |

## Out of scope

- `transitive` and anything that follows chains of links: queries belong to the read API (GitHub issue #9).
- Cardinality on relations (`functional`, "at most one incoming").
- Source or target types declared on the relation (RDF domain and range); [0010](../decisions/0010-concept-files-and-reference-properties.md) keeps `target` on the property.
- Storing inverse links on the target; [0003](../decisions/0003-source-side-relations.md) stands.
- Outgoing references in `knott refs` for non-symmetric relations; the entity's own frontmatter already shows them.

## Compatibility

Additive. Vaults without `.knott/relations/` behave exactly as in 0.5.0, except that `knott refs` exists. A vault that created `.knott/relations/` or used `relation:` got an error in 0.5.0 and now gets these definitions checked instead. Ontology API additions only. Version 0.6.0.

The docs vault adopts it in the same change: `about` (inverse `discussed_in`, named by `decision.affects` and `issue_code.about`), `related` (symmetric, on `concept.related`), `supersedes` (inverse `superseded_by`, acyclic, on `decision.supersedes` and `spec.supersedes`), and `amends` (inverse `amended_by`, acyclic, on `decision.amends` and `spec.amends`).
