---
type: guide
title: Python API
audience: developer
concepts:
  - "[Vault](../concepts/vault.md)"
  - "[Issue](../concepts/issue.md)"
  - "[Relation](../concepts/relation.md)"
---
# Python API

The CLI is a thin adapter over the `knott` package; everything it does is available in Python.

```python
from knott import Knott

vault = Knott.open(".")             # walks up to the vault root
result = vault.validate()           # or vault.validate(["transcripts/foo.md"])

result.ok                           # bool
result.stats                        # Stats(schemas=…, entities=…, relations=…)
for issue in result.issues:         # sorted by path, then line
    print(issue.code, issue.path, issue.line, issue.field, issue.message)

vault.types()                       # ["concept", "decision", …]
vault.schemas()                     # [SchemaInfo(type, description, path), …]
vault.schema_issues()               # problems from schema loading only
vault.ontology()                    # Ontology(vault, types, schema_issues, relations)
vault.refs("concepts/kid.md")       # Refs(entity, groups): who references it; also "kid:<uuid>"
vault.entities("spec", where={"status": "draft"})  # [EntityRecord(path, type, kid, properties), …]
vault.show("concepts/kid.md")       # EntityDetail(entity, references, referenced_by, body)
vault.loops()                       # [LoopReport(loop, stages, exits, unplaced), …]; loops("name") for one
vault.migrate()                     # convert .knott/schemas/; MigrateResult(written, removed, list_fields)
vault.validate(fix=True)            # add missing kids first; result.fixed: [FixedEntity(path, kid)]
Knott.init("new-vault")             # InitResult(root, created)
```

## Contract

- Inputs and outputs are plain data: `str`, `Path`, ints, lists, and frozen Pydantic models. No parser objects leak out.
- `validate()` **never raises for validation problems**. They're returned as `Issue`s.
- It raises only for exit-code-2 conditions, all subclasses of `KnottError`: `VaultNotFoundError`, `ConfigError`, `PathNotFoundError`, `PathOutsideVaultError`, and `MigrateError` from `migrate()`.
- Relative paths passed to `validate()`, `refs()`, `show()` and a reference value of `entities(where=…)` are resolved against the vault root (the CLI resolves them against the current directory first).

`ontology()` returns `Ontology(vault, types, schema_issues, relations, connectors, loops)`. Each `OntologyType` has `type`, `description`, `path` (its concept file), `count` (entities of that type; files with invalid frontmatter are not counted), `extends`, `abstract`, `ancestors`, `subtypes` and `inherited` (which ancestor an inherited `template`, `path`, `filename` or `kid` comes from), `kid_required`, `entity_paths` (the folder patterns of the concept's `path`, `[]` when it has none), `filename` (`FilenamePattern(pattern, parts)` or `None`; each part is `FilenamePart(name, match, description)`), `properties` (in concept-file order) and `template` (the concept file's body, `None` when blank).

An `OntologyAttribute` mirrors its definition: `name`, `inherited_from` (the ancestor that declares an inherited top-level property), `type` (a scalar name, or `list`, `object`, `map`, `reference`, `file` or `enum`), `required` and `description`. A `list` has its item definition in `items`, a `map` its value definition in `values`, and an `object` its fields in `fields`, recursively; the `items` / `values` nodes have `name=None`. A `reference` has `open` (declared `target: any`, with `targets` empty), `targets`, the types some concept defines, `unknown_targets`, the ones none does (shown, never enforced), and `relation`, the relation it names (`None` when it names none, or one no relation file defines). An `enum` has `options`, a list of `EnumOption(value, description)` in concept order. A `file` has `accept`, the extensions a vault file may have (`[]` when any). `attribute.notation` gives the compact form, e.g. `list of object` or `reference → episode | meeting`.

`OntologyType.references()` lists every reference at any depth as `(path, attribute)` pairs, in concept-file order. Paths use `[]` for a list's items, `.*` for a map's values and `.field` for an object's fields:

```python
t = next(t for t in vault.ontology().types if t.type == "transcript")
[(path, a.targets) for path, a in t.references()]
# [("derived_from", ["script"]), ("sources[]", ["script"]), ("speakers[].person", ["person"])]
```

`knott types --verbose` prints the same paths, and `knott view` draws one edge per known target.

`Ontology.relations` lists every relation file, sorted by name, as `RelationDefinition(name, description, inverse, symmetric, acyclic, guidance, path)`; it is `[]` for a vault without relation files. `Ontology.connectors` lists every [connector file](../concepts/file.md#uris-and-connectors) the same way, as `ConnectorDefinition(name, description, guidance, path)`. `Ontology.loops` lists every [loop](../concepts/loop.md) as `LoopDefinition(name, description, type, property, stages, exits, guidance, path)`.

`loops()` returns what [`knott loops`](../commands/loops.md) prints: per loop, a `LoopReport` whose `stages` and `exits` are `LoopPlacement(stage, entities)` and whose `unplaced` holds entities with no stage. Each `LoopEntity(path, kid, title, type, unmet, next, missing_next)` lists its unmet needs and what the next stage still misses as `LoopNeed(kind, property, inverse, relation, type, since)`.

## Entities as data

`entities()` returns what [`knott list`](../commands/list.md) prints, and `show()` what [`knott show`](../commands/show.md) prints. Neither validates.

```python
import datetime as dt

vault.entities()                                   # every entity, ordered by path
vault.entities("concept")                          # a type and its subtypes
vault.entities("spec", where={"status": "draft"}, fields=["title", "created_on"])
# [EntityRecord(path="specs/0017-….md", type="spec", kid=None,
#               properties={"title": "0017: …", "created_on": datetime.date(2026, 11, 26)}), …]
vault.entities("decision", where={"affects": "concepts/relation.md"})   # by a reference's target
vault.entities("spec", where={"released_in": None})                     # the property is absent
vault.entities("task", where=[("tags", "red"), ("tags", "blue")])       # one key twice: pairs
```

- **`where` values are typed**, not text: an `int` for an `integer`, a `float` or `int` for a `number`, a `bool`, a `datetime.date`, a `datetime.datetime`, a `str` for a string, enum option or file, and an entity path (relative to the vault root) or `"kid:<uuid>"` for a reference. `None` means "absent". A value of another kind raises `KnottError`, as do a type no concept defines, `where` without a type, and a key that is not a top-level property of the type.
- **`properties` is `None` without `fields`.** With `fields`, it holds those keys in that order, `None` for a key the entity lacks.
- **Values are as written**: nothing is converted to the declared type, a reference stays the text in the file, and a blank value is `None`. Dates are `datetime.date`; `record.model_dump(mode="json")` gives `"2026-11-26"`.

```python
detail = vault.show("specs/0006-relation-definitions.md", body=True)
detail.entity.properties["status"]        # "implemented"; every key but `type` and `kid`
detail.references[-1]
# OutgoingRef(field="amends[0]", relation="amends", value="[0005](0005-concept-files.md)",
#             path="specs/0005-concept-files.md", type="spec", kid=None, error=None)
detail.referenced_by                      # list[RefGroup], the groups of refs()
detail.body                               # the body, verbatim; None when blank or not asked for
```

`OutgoingRef.error` is the issue code `validate()` reports for that value (`relation-target-not-found`, `relation-target-type-mismatch`, …), or `None`. `path`, `type` and `kid` are `None` when the value resolves to no file; `type` and `kid` are `None` when the file is not an entity. `show()` raises as `refs()` does.

## Reverse lookup

`refs()` takes an entity path or `kid:<uuid>` and returns what [`knott refs`](../commands/refs.md) prints:

```python
refs = vault.refs("concepts/kid.md")
refs.entity                         # EntityRef(path="concepts/kid.md", type="concept", kid=None)
[(g.label, g.kind, len(g.references)) for g in refs.groups]
# [("discussed_in", "inverse", 4), ("related", "symmetric", 3), ("← spec.concepts[]", "property", 1)]
refs.groups[0].references[0]        # Ref(path="decisions/0009-kid-identity.md", type="decision",
                                    #     kid=None, field="affects[0]", line=7, direction="in")
```

It doesn't validate, and raises `PathNotFoundError`, `PathOutsideVaultError` or `KnottError` when the path isn't an entity or a `kid:` matches no entity or several.

`migrate()` runs before anything is loaded, so it works on a vault that reports `schema-legacy-layout`. It raises `MigrateError` and writes nothing when it refuses (see [knott migrate](../commands/migrate.md)).

## Layout

```
src/knott/
  api.py        Knott class: open / init / migrate / validate / types / schemas / schema_issues / ontology / refs / entities / show / loops
  cli.py        thin Typer adapter
  view.py       render_ontology(): Ontology → self-contained HTML (template in _view/)
  models.py     Issue, Stats, ValidationResult, SchemaInfo, InitResult, MigrateResult,
                Ontology, OntologyType, OntologyAttribute, RelationDefinition,
                ConnectorDefinition, EnumOption,
                Refs, EntityRef, RefGroup, Ref,
                LoopDefinition, LoopStage, LoopNeed, LoopReport, LoopPlacement, LoopEntity
  errors.py     KnottError hierarchy
  schema/       loader (concept files), relations (relation files and their checks),
                connectors (connector files), loops (loop files and their checks),
                validator (entities vs schemas), migrate (.knott/schemas/ → concepts)
  vault/        discovery, entity (frontmatter), links (resolve_reference),
                files (resolve_file), index (the vault's
                references, built once per run), cycles (relation-cycle), refs (reverse lookup), query (list and show),
                loops (placement by stage, loop-stage-unmet)
```
