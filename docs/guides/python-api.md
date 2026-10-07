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
Knott.init("new-vault")             # InitResult(root, created)
```

## Contract

- Inputs and outputs are plain data: `str`, `Path`, ints, lists, and frozen Pydantic models. No parser objects leak out.
- `validate()` **never raises for validation problems**. They're returned as `Issue`s.
- It raises only for exit-code-2 conditions, all subclasses of `KnottError`: `VaultNotFoundError`, `ConfigError`, `PathNotFoundError`, `PathOutsideVaultError`.
- Relative paths passed to `validate()` are resolved against the vault root (the CLI resolves them against the current directory first).

`ontology()` returns `Ontology(vault, types, schema_issues)`. Each `OntologyType` has `type`, `description`, `path`, `count` (entities of that type; files with invalid frontmatter are not counted), `attributes` and `relations`. Relations to types with no schema come last, with `target_known=False`.

## Layout

```
src/knott/
  api.py        Knott class: open / init / validate / types / schemas / schema_issues / ontology
  cli.py        thin Typer adapter
  view.py       render_ontology(): Ontology → self-contained HTML (template in _view/)
  models.py     Issue, Stats, ValidationResult, SchemaInfo, InitResult,
                Ontology, OntologyType, OntologyAttribute, OntologyRelation
  errors.py     KnottError hierarchy
  schema/       loader (discovery + parsing), validator (entities vs schemas)
  vault/        discovery, entity (frontmatter), links (resolve_reference)
```
