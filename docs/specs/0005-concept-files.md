---
type: spec
title: "0005: Define types in concept files, with references as properties"
status: implemented
created_on: 2026-11-23
released_in: "0.5.0"
github_issues:
  - 1
decisions:
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
  - "[0008](../decisions/0008-structured-attributes.md)"
  - "[0005](../decisions/0005-empty-values.md)"
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Attribute](../concepts/attribute.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Ontology](../concepts/ontology.md)"
  - "[Vault](../concepts/vault.md)"
amends:
  - "[0001](0001-ontology-viewer.md)"
  - "[0003](0003-structured-attributes.md)"
  - "[0004](0004-kid-identity.md)"
---
# 0005: Define types in concept files, with references as properties

## Summary

Each type is now defined by a Markdown concept file in `.knott/concepts/`. Its frontmatter is the schema and its optional body is a template for entity bodies. `attributes` and `relations` merge into one `properties` map, where a reference is a shape (`type: reference`) usable at any depth, with one or several target types and strict cardinality. This breaks the schema format and the Python ontology API: a vault with `.knott/schemas/` reports `schema-legacy-layout` until `knott migrate` converts it. Entities stay compatible, except where strict cardinality now rejects them.

## Behaviour

### Concept files

```markdown
---
name: transcript
description: Transcript of recorded spoken content.
kid: required
properties:
  title:        { type: string, required: true }
  derived_from: { type: reference, target: script }
  sources:
    type: list
    items: { type: reference, target: [script, episode] }
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

- Knott reads `.knott/concepts/**/*.md`. Subfolders are only for organisation. Other file types there are ignored.
- Top-level keys: `name` (required, `^[a-z][a-z0-9_-]*$`), `description`, `kid` (`required` only, as in [0004](0004-kid-identity.md)), `properties` (a map of name to definition). Nothing else.
- Entities keep `type: <name>`.
- Top-level property names `type` and `kid` are reserved; nested object fields may use them.
- The body, after the frontmatter, is stored verbatim as the type's template. A blank body is no template. Knott never checks an entity's body against it.
- A concept file is not an entity: `.knott/` is never scanned for entities, and running knott on a concept file directly reports `not-an-entity`.

Targeted messages for common mistakes, all `schema-invalid-field` unless noted:

| In a concept file | Message |
|---|---|
| `type:` | ``unknown key `type` in concept file: concept files use `name:`; `type:` belongs to entities`` |
| `attributes:` or `relations:` | ``unknown key `attributes` in concept file: merged into `properties` (decision 0010); run `knott migrate` `` |
| no frontmatter (`schema-invalid-yaml`, line 1) | ``a concept file needs YAML frontmatter: start the file with a `---` line, then `name: <type>`, then a closing `---` line`` |
| two files with one `name` (`schema-duplicate-type`) | ``concept `a` is defined twice: in `.knott/concepts/a.md` and in `.knott/concepts/sub/a2.md` `` |
| a top-level property named `kid` or `type` | ``a property cannot be named `kid`; it is reserved for the knott-managed entity identity`` |

### Reference shape

`type: reference` is a shape like `string` or `list`, allowed anywhere a shape is: top-level, list `items`, map `values`, object `fields`.

- Keys: `type`, `target` (required), `required`, `description`. `required` stays forbidden on `items` and `values` ([0003](0003-structured-attributes.md)).
- `target` is a type name or a non-empty list of unique type names (`target: [episode, meeting]`). An empty list, a repeated name, a non-string, or a missing `target` is `schema-invalid-field`.
- A target no concept defines is `schema-unknown-target`, once per unknown name, with `field` set to the full schema path (`properties.sources.items.target`). The name is dropped from the targets. If no known target is left, the reference keeps its shape, so the value kind and path are still checked, but the target-type check is skipped.
- Reserved for relation definitions ([0010](../decisions/0010-concept-files-and-reference-properties.md) §7), not built yet:
  - a `relation:` key on a reference: ``` `relation` is reserved for relation definitions, not supported yet (decision 0010); remove it ```
  - a `.knott/relations/` folder, reported at path `.knott/relations`: ``` `.knott/relations/` is reserved for relation definitions (decision 0010), not supported yet ```

### Validating reference values

Cardinality is strict. `reference` holds one; several is a `list` of `reference`.

| Value | `reference` | `list` of `reference` |
|---|---|---|
| `null`, `""` | absent | absent |
| `[]` | `relation-invalid-value` (empty list; leave the value empty) | absent |
| `{}` | `relation-invalid-value` | `relation-invalid-value` |
| a string | resolved | `relation-invalid-value`: write a list, even for one |
| a list | `relation-invalid-value`: declare `type: list` for several | each item resolved; a `null` or empty item is `relation-invalid-value` |

- An absent required reference is `relation-missing`. So is an absent required list or map whose items (at any depth) are references: such a container counts as a reference property, and its wrong-kind values, empty items and non-string map keys are `relation-invalid-value`. An empty map of references is absent.
- Any other container keeps the `attribute-*` codes, even if references sit inside its objects. Only the reference fields themselves use `relation-*`.
- A resolved reference passes the type check when the entity's type is one of the known targets. The mismatch message lists all of them.
- Resolution itself is unchanged, including `kid:` references, which now also work at any depth.
- `field` is the full path (`speakers[1].person`, `hosts.main`, `includes[0]`) and `line` is the nested key or item. This applies to top-level list references too, which used to report just the property name.
- Stats count every resolved reference at any depth, including one whose targets are all unknown.

```
✗ e/a.md:3  one
  relation `one` expects target type `d` or `c`
  but `x.md` has type `x`

✗ e/a.md:4  many
  relation `many` expects list of reference → c but got string `[a](a.md)`; write it as a list of references, even for one

✗ e/t.md:4  about
  relation `about` expects one reference but got a list; declare `type: list` with reference `items` for several

✗ e/t3.md:4  about
  relation `about` expects one reference but got an empty list; leave the value empty when there is none

✗ e/b.md:4  many[1]
  relation `many[1]` is an empty list item; remove it or give it a reference

✗ e/c.md:3  many
  required relation `many` (list of reference → c) is missing or empty; add at least one reference

✗ e/t.md:7  speakers[1].person
  required relation `speakers[1].person` (reference → person) is missing or empty; add a reference
```

### Legacy layout

If `.knott/schemas/` exists, every run reports one issue and stops: no concept files are loaded and no entities are checked, so entities don't also report `entity-unknown-type`.

```
✗ .knott/schemas
  `.knott/schemas/` is the pre-0.5 schema layout; knott now reads concept files from `.knott/concepts/` (decision 0010)
  run `knott migrate` to convert the schemas, then review the diff

1 validation error
```

`validate` exits `1` with zero stats. `types` prints no types, reports the issue and exits `1`. `view` writes no page, prints the issue to stderr and exits `1`. The issue has no line or field.

### Ontology and references

A reference path names where a reference sits in a type's properties: `[]` for list items, `.*` for map values, `.field` for object fields (`derived_from`, `sources[]`, `speakers[].person`, `hosts.*`). A reference is *required along its path* when every named step on the way is required. A list's items take the list's `required`; an object field is required only if it and every enclosing property are.

## Issue codes

| Code | Stage | When | `field` | `line` |
|---|---|---|---|---|
| `schema-legacy-layout` (new) | schema | `.knott/schemas/` exists; the only issue of the run | none | none |
| `schema-field-conflict` (removed) | | one map can't hold a name twice; reserved names are now `schema-invalid-field` | | |
| `schema-invalid-field` (changed) | schema | the concept-file key rules, reference keys and targets above, and `.knott/relations/` (path `.knott/relations`) | full schema path | that key |
| `schema-invalid-yaml` (changed) | schema | also a concept file with no frontmatter | none | `1` |
| `schema-unknown-target` (changed) | schema | per unknown name, at any depth | full path to `target` | the `target` key, or the list item naming it |
| `schema-duplicate-type` (changed) | schema | two concept files with one `name`; the message names both | `name` | `name:` of the later file |
| `relation-missing` (changed) | entity | a required reference, or a required container of references, is absent | full path | nested key |
| `relation-invalid-value` (changed) | entity | the cardinality and emptiness table above, at any depth | full path | nested key or item |
| `relation-target-*` (changed) | entity | as before, at any depth; a type mismatch lists every known target | full path | nested key or item |

## CLI and API

### `knott migrate [PATH]`

Converts a pre-0.5 vault. `PATH` is any path inside the vault. It runs without loading schemas, so it works on a vault that reports `schema-legacy-layout`.

For each `.knott/schemas/**/*.yaml`, read with the safe loader and its limits, it writes `.knott/concepts/<same relative path>.md`:

- `type` becomes `name`. `description` and `kid` are kept.
- `attributes`, then `relations`, go into `properties`, each in file order. Attribute definitions are copied as they are.
- A relation becomes `{type: reference, target, required, description}`. If any entity of that type stores a YAML list in that field, it becomes `{type: list, required, description, items: {type: reference, target}}`, with `required` on the list.
- Output YAML is block style with keys in that order, never wrapped, multi-line strings folded (`>`). The body is empty.

Then it deletes `.knott/schemas/`, validates the vault and prints both:

```
$ knott migrate
+ .knott/concepts/compilation.md
+ .knott/concepts/media/episode.md
+ .knott/concepts/script.md
  list of reference: compilation.sources
- .knott/schemas/

✓ 3 schemas
✓ 4 entities
✓ 4 relations
✓ vault is valid
```

It checks everything before writing anything. It refuses with `error: …`, exit `2`, changing nothing, when:

- there is no `.knott/schemas/` folder (``nothing to migrate: <root> has no `.knott/schemas/` folder``)
- `.knott/schemas/` is a symbolic link; it is never followed or deleted
- a schema file can't be read, isn't UTF-8 or isn't valid YAML (`<file>:<line>: …`)
- a schema isn't a mapping, lacks `type`, has an unknown key at the top level or in a relation, a relation lacks `target`, or a name is under both `attributes` and `relations`
- `.knott/schemas/` holds a non-hidden file that isn't `.yaml`, which the delete would lose; hidden files such as `.DS_Store` are deleted with the folder
- a concept file it would write already exists
- a path on the way to a concept file, `.knott/concepts` itself included, exists but isn't a folder (``.knott/concepts/media is not a folder; move it away or delete it, …``)

If writing a concept file fails (disk full, no permission), the files and the folders migrate created are removed again, folders that existed before are kept, and it prints ``cannot write concept files: <file>: <reason>; nothing was changed``, exit `2`.

If every concept file is written but `.knott/schemas/` can't be deleted, the concept files are kept, since the delete may already have removed some legacy files, and it prints ``concept files written, but `.knott/schemas/` could not be removed: …; delete `.knott/schemas/` by hand``, exit `2`.

| Exit | Meaning |
|---|---|
| `0` | migrated, vault valid |
| `1` | migrated, vault has validation issues |
| `2` | refused or failed as above, or no vault found |

`migrate` has no `--format json` and doesn't change `.knott/config.yaml`.

### Other commands

- `knott init` creates `.knott/concepts/` instead of `.knott/schemas/`.
- `knott types --verbose` prints, per type: the concept file, description, `kid: required` when set, `template: yes|no`, `references: <paths>` (or `none`), then one `properties:` list in schema order. A reference shows `→` and its targets; an unknown target is marked `(unknown)`. With no types it prints nothing.

```
lexeme  (.knott/concepts/lexeme.md)
  A word with its senses and forms.
  kid: required
  template: yes
  references: senses[].see_also, topic
  properties:
    lemma*   string
    tags     list of string
    senses*  list of object
      each item: One sense per meaning.
      id*       string
      ru*       string              Russian gloss
      see_also  reference → lexeme
    forms    map of map of string
    topic*   reference → topic | lesson (unknown)
```

- `knott view` draws one edge per known target of every reference, at any depth, labelled with its path. An edge is solid when the reference is required along its path. Unknown targets get no edge and no ghost node; the panel lists them as `<name> (unknown)`. The panel shows one Properties table (known targets are links), the template in a collapsible block, References and Referenced by. The no-types error now reads `error: no types to show (add concept files to .knott/concepts/)`.

### Python API

- `OntologyAttribute.type` may be `reference`. It gains `targets: list[str]` (known targets, empty unless a reference) and `unknown_targets: list[str]`. Notation: `reference → script`, `list of reference → script | episode`; a reference with no known target is plain `reference`.
- `OntologyType.attributes` and `.relations` are replaced by `properties: list[OntologyAttribute]` in schema order. It gains `template: str | None` and `references() -> list[tuple[str, OntologyAttribute]]` (path and reference node, in schema order).
- `OntologyRelation` is removed. `SchemaInfo.path` points at the concept file.
- `Knott.migrate() -> MigrateResult(written: list[str], removed: str, list_fields: list[str])`. `written` holds the vault-relative concept paths, sorted by source path; `removed` is `.knott/schemas`, and `list_fields` are `<type>.<field>` names of relations converted to lists. Failures raise `MigrateError`, a `KnottError`. Both are exported from `knott`.

## Edge cases

- `target: [episode, meeting]` with `meeting` undefined: one `schema-unknown-target`; an `episode` passes, any other type is `relation-target-type-mismatch`.
- All targets unknown: the value must still be one resolvable reference; any entity type passes.
- A `list of object` whose objects hold references: the list uses `attribute-*` codes; `speakers[1].person` uses `relation-*`.
- `kid:` references inside list items and map values: resolved, with full `field` path and line.
- A concept body with only whitespace, or no trailing newline after the closing `---`: `template` is `None`.
- A vault with both `.knott/schemas/` and entities: one `schema-legacy-layout`, nothing else.
- `migrate` on a vault where an entity stores a list in only one of many files: the relation becomes a list, and entities holding a single reference there now get `relation-invalid-value`.
- `migrate` with an empty `.knott/schemas/` holding only `.DS_Store`: writes nothing, creates `.knott/concepts/`, deletes the folder.
- A concept file run through `knott validate <file>`: `not-an-entity`.

## Out of scope

- Checking entity bodies against the template; placeholder syntax in templates.
- Relation definition files (`.knott/relations/`, the `relation:` key), reverse lookup and `inverse`, `symmetric`, `acyclic`, `transitive`; they wait for the read API (#9).
- Cardinality keywords (`min_items`, `functional`).
- A `--format json` output for `migrate`.

## Compatibility

Breaking, for the schema format and the Python ontology API.

- Every vault must run `knott migrate` once and review the diff. Until then every command reports `schema-legacy-layout`.
- Entities don't change. Strict cardinality rejects a single value where a list of references is declared, or a list where one reference is declared; `migrate` picks the shape that fits current data.
- Python: replace `OntologyType.attributes` / `.relations` with `.properties` and `references()`; `OntologyRelation` is gone.
- `schema-field-conflict` no longer exists.

Released as 0.5.0.
