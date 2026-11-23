---
type: guide
title: Python API
audience: developer
concepts:
  - "[Vault](../concepts/vault.md)"
  - "[Issue](../concepts/issue.md)"
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
vault.ontology()                    # Ontology(vault, types, schema_issues)
vault.migrate()                     # convert .knott/schemas/; MigrateResult(written, removed, list_fields)
vault.validate(fix=True)            # add missing kids first; result.fixed: [FixedEntity(path, kid)]
Knott.init("new-vault")             # InitResult(root, created)
```

## Contract

- Inputs and outputs are plain data: `str`, `Path`, ints, lists, and frozen Pydantic models. No parser objects leak out.
- `validate()` **never raises for validation problems**. They're returned as `Issue`s.
- It raises only for exit-code-2 conditions, all subclasses of `KnottError`: `VaultNotFoundError`, `ConfigError`, `PathNotFoundError`, `PathOutsideVaultError`, and `MigrateError` from `migrate()`.
- Relative paths passed to `validate()` are resolved against the vault root (the CLI resolves them against the current directory first).

`ontology()` returns `Ontology(vault, types, schema_issues)`. Each `OntologyType` has `type`, `description`, `path` (its concept file), `count` (entities of that type; files with invalid frontmatter are not counted), `kid_required`, `properties` (in concept-file order) and `template` (the concept file's body, `None` when blank).

An `OntologyAttribute` mirrors its definition: `name`, `type` (a scalar name, or `list`, `object`, `map` or `reference`), `required` and `description`. A `list` has its item definition in `items`, a `map` its value definition in `values`, and an `object` its fields in `fields`, recursively; the `items` / `values` nodes have `name=None`. A `reference` has `targets`, the types some concept defines, and `unknown_targets`, the ones none does (shown, never enforced). `attribute.notation` gives the compact form, e.g. `list of object` or `reference → episode | meeting`.

`OntologyType.references()` lists every reference at any depth as `(path, attribute)` pairs, in concept-file order. Paths use `[]` for a list's items, `.*` for a map's values and `.field` for an object's fields:

```python
t = next(t for t in vault.ontology().types if t.type == "transcript")
[(path, a.targets) for path, a in t.references()]
# [("derived_from", ["script"]), ("sources[]", ["script"]), ("speakers[].person", ["person"])]
```

`knott types --verbose` prints the same paths, and `knott view` draws one edge per known target.

`migrate()` runs before anything is loaded, so it works on a vault that reports `schema-legacy-layout`. It raises `MigrateError` and writes nothing when it refuses (see [knott migrate](../commands/migrate.md)).

## Layout

```
src/knott/
  api.py        Knott class: open / init / migrate / validate / types / schemas / schema_issues / ontology
  cli.py        thin Typer adapter
  view.py       render_ontology(): Ontology → self-contained HTML (template in _view/)
  models.py     Issue, Stats, ValidationResult, SchemaInfo, InitResult, MigrateResult,
                Ontology, OntologyType, OntologyAttribute
  errors.py     KnottError hierarchy
  schema/       loader (concept files), validator (entities vs schemas), migrate (.knott/schemas/ → concepts)
  vault/        discovery, entity (frontmatter), links (resolve_reference)
```
