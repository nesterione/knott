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
vault.migrate()                     # convert .knott/schemas/; MigrateResult(written, removed, list_fields)
vault.validate(fix=True)            # add missing kids first; result.fixed: [FixedEntity(path, kid)]
Knott.init("new-vault")             # InitResult(root, created)
```

## Contract

- Inputs and outputs are plain data: `str`, `Path`, ints, lists, and frozen Pydantic models. No parser objects leak out.
- `validate()` **never raises for validation problems**. They're returned as `Issue`s.
- It raises only for exit-code-2 conditions, all subclasses of `KnottError`: `VaultNotFoundError`, `ConfigError`, `PathNotFoundError`, `PathOutsideVaultError`, and `MigrateError` from `migrate()`.
- Relative paths passed to `validate()` and `refs()` are resolved against the vault root (the CLI resolves them against the current directory first).

`ontology()` returns `Ontology(vault, types, schema_issues, relations, connectors)`. Each `OntologyType` has `type`, `description`, `path` (its concept file), `count` (entities of that type; files with invalid frontmatter are not counted), `kid_required`, `properties` (in concept-file order) and `template` (the concept file's body, `None` when blank).

An `OntologyAttribute` mirrors its definition: `name`, `type` (a scalar name, or `list`, `object`, `map`, `reference` or `file`), `required` and `description`. A `list` has its item definition in `items`, a `map` its value definition in `values`, and an `object` its fields in `fields`, recursively; the `items` / `values` nodes have `name=None`. A `reference` has `targets`, the types some concept defines, `unknown_targets`, the ones none does (shown, never enforced), and `relation`, the relation it names (`None` when it names none, or one no relation file defines). A `file` has `accept`, the extensions a vault file may have (`[]` when any). `attribute.notation` gives the compact form, e.g. `list of object` or `reference → episode | meeting`.

`OntologyType.references()` lists every reference at any depth as `(path, attribute)` pairs, in concept-file order. Paths use `[]` for a list's items, `.*` for a map's values and `.field` for an object's fields:

```python
t = next(t for t in vault.ontology().types if t.type == "transcript")
[(path, a.targets) for path, a in t.references()]
# [("derived_from", ["script"]), ("sources[]", ["script"]), ("speakers[].person", ["person"])]
```

`knott types --verbose` prints the same paths, and `knott view` draws one edge per known target.

`Ontology.relations` lists every relation file, sorted by name, as `RelationDefinition(name, description, inverse, symmetric, acyclic, guidance, path)`; it is `[]` for a vault without relation files. `Ontology.connectors` lists every [connector file](../concepts/file.md#uris-and-connectors) the same way, as `ConnectorDefinition(name, description, guidance, path)`.

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
  api.py        Knott class: open / init / migrate / validate / types / schemas / schema_issues / ontology / refs
  cli.py        thin Typer adapter
  view.py       render_ontology(): Ontology → self-contained HTML (template in _view/)
  models.py     Issue, Stats, ValidationResult, SchemaInfo, InitResult, MigrateResult,
                Ontology, OntologyType, OntologyAttribute, RelationDefinition,
                ConnectorDefinition,
                Refs, EntityRef, RefGroup, Ref
  errors.py     KnottError hierarchy
  schema/       loader (concept files), relations (relation files and their checks),
                connectors (connector files),
                validator (entities vs schemas), migrate (.knott/schemas/ → concepts)
  vault/        discovery, entity (frontmatter), links (resolve_reference),
                files (resolve_file), index (the vault's
                references, built once per run), cycles (relation-cycle), refs (reverse lookup)
```
