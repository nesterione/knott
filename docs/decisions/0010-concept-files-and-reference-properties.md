---
type: decision
title: Concepts are Markdown files, and references are properties
status: accepted
decided_on: 2026-11-23
affects:
  - "[Schema](../concepts/schema.md)"
  - "[Attribute](../concepts/attribute.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Ontology](../concepts/ontology.md)"
---
# 0010: Concepts are Markdown files, and references are properties

**Context.** A type was defined by a YAML file in `.knott/schemas/`, with two maps: `attributes` (values, nested shapes from [0008](0008-structured-attributes.md)) and `relations` (`target`, `required`, `description`). The split cost more than it gave:

- The two maps already shared one namespace (`schema-field-conflict`).
- A relation couldn't appear inside a structured value, a gap 0008 left open.
- A relation silently accepted one reference or a list, the only definition whose shape depended on the value written.
- Union targets (GitHub issue #1) needed a third form.

The schema file also had no place for what a good entity *body* looks like, which is what an agent needs most when it writes one.

**Decision.**

1. **Concept files.** Each type is defined by one Markdown file in `.knott/concepts/**/*.md`. Its frontmatter is the schema. Its body is optional: a template for the body of entities of that type, with `<!-- … -->` comments explaining each section. Subfolders are only for organisation.
2. **Identity is `name:`.** A concept file says `name: transcript`, and entities keep `type: transcript`. A concept file can't be mistaken for an entity. Two concept files with the same `name` are an error that names both.
3. **The body is guidance only.** Agents and future commands (`knott new`) copy it. Knott never checks an entity's body against it. The body is plain Markdown, with no placeholder syntax.
4. **One `properties` map.** `attributes` and `relations` are replaced by `properties`. A reference is a property whose shape is `type: reference` with a `target`:

   ```yaml
   ---
   name: transcript
   description: Transcript of recorded spoken content.
   properties:
     title:        { type: string, required: true }
     derived_from: { type: reference, target: script }
     speakers:
       type: list
       items:
         type: object
         fields:
           person: { type: reference, target: person }
           role:   { type: string }
   ---
   # Transcript

   <!-- One paragraph: who speaks and what it covers. -->
   ```

   A `reference` shape can appear anywhere a shape can: at the top level, as list `items`, as a map's `values`, or as an object field. `target` is one type name or a list of type names (`target: [episode, meeting]`).
5. **Cardinality is strict.** `type: reference` holds exactly one reference. Several is `type: list` with `items: { type: reference, … }`, and `required: true` on the list means "at least one". A list given where one reference is declared is `relation-invalid-value`, and so is a single reference given where a list is declared.
6. **Issue codes stay.** `relation-*` codes report any property with a reference shape, at any depth: `relation-missing` for a required one, `relation-invalid-value` for a value of the wrong kind, and the `relation-target-*` codes for resolution, which is unchanged ([reference resolution](../concepts/reference-resolution.md)). `field` holds the full path (`speakers[1].person`). `attribute-*` codes report every other property. `schema-*` codes keep their names for problems in concept files. `schema-field-conflict` is retired, because one map can't hold a name twice.
7. **Relation definitions are the agreed direction, not built yet.** The `relation:` key on a reference shape and the `.knott/relations/` folder are reserved: using either is an error. When reverse lookup (#9) lands, a relation file will hold what a link means, shared by every property that names it:

   ```yaml
   # .knott/relations/supersedes.md
   ---
   name: supersedes
   inverse: superseded_by
   acyclic: true
   description: This entity replaces the target. The target stays as history.
   ---
   ```

   ```yaml
   # in a concept file
   supersedes: { type: reference, target: decision, relation: supersedes }
   ```

   These rules are fixed now, so the format won't need another break:
   - A concept file still lists every key its entities may have. A relation file declares no source or target types and never adds a key to a concept. `target` belongs to the property.
   - Relation keys are closed: `name`, `description`, `inverse`, `symmetric`, `acyclic`, `transitive`. The body explains when to use the relation.
   - `inverse` and `symmetric` change how a link is *read* (reverse lookup, `knott view`, export). They never store anything on the target, so [0003](0003-source-side-relations.md) holds.
   - `acyclic` is checked by `knott validate` across every property that names the relation. `transitive` affects queries only.
   - Errors: `relation-unknown` (a property names an undefined relation), `relation-inverse-conflict` (an `inverse` equals a property name on a target concept), `relation-symmetric-mismatch` (a symmetric relation used on a property whose targets don't include its own concept, or a symmetric relation with an `inverse`), `relation-cycle`.
   - Many properties may name one relation, in one concept or across concepts, under any key names.
8. **Migration is a hard switch.** Knott reads only `.knott/concepts/`. If `.knott/schemas/` exists, every run reports `schema-legacy-layout` and points at `knott migrate`. That command writes one concept file per YAML schema, then removes `.knott/schemas/`:
   - `type` becomes `name`.
   - `attributes` and `relations` merge into `properties`, attributes first, in file order.
   - A relation becomes `type: reference`. It becomes a `list` of references if any current entity stores a list in that field, and stays a single reference otherwise.
   - The body is left empty.

**Not included.** Checking entity bodies against the template. Placeholders in the template. Relation files themselves (wait for #9). Cardinality keywords (`min_items`, `functional`).

**Why.**

- **Markdown files:** the type, its rules and the shape of a good entity sit in one file that humans, Obsidian and agents all read. `<!-- -->` comments stay out of Obsidian's reading view when an entity is made from the template.
- **`name:`:** frontmatter with `type: transcript` reads as a transcript entity to every tool that knows entities, including knott run on that file directly.
- **One map:** a reference is a value that points somewhere, so it uses the same shape system as every other value. That closes 0008's gap and #1 with no new concepts.
- **Strict cardinality:** the same rule as every other shape ([0004](0004-strict-typing.md)), and readers of the vault (#9) get a predictable type.
- **Relations later:** none of their rules is needed by a current vault. Reserving the names now costs nothing and avoids a second format break.
- **Domain and range stay on the property:** if relation files owned them (RDF style), a concept's allowed keys would be spread across many files, which would weaken both closed-world validation and the "read one concept file before writing" workflow.

**Consequences.**

- Every existing schema must be migrated once. Entities don't change, except where strict cardinality now rejects a single value for a list reference or a list for a single reference. `knott migrate` picks the shape that fits current data, so this only affects entities written later.
- The graph is no longer a separate block in the file. `knott types --verbose` and `knott view` list a type's references, nested ones included, as a section of their own.
- The Python API changes: `OntologyType.attributes` and `.relations` become one `properties` list, and the Python `RelationDef` goes away. The ontology view derives edges by walking shapes.
- "Schema" remains the word for the frontmatter contract. A *concept* is the type, and its concept file holds its schema.
- `knott migrate` writes files in `.knott/`. That is knott's own configuration, so the "only edit to user files" rule in [0009](0009-kid-identity.md) still describes entities.
