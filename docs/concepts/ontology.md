---
type: concept
title: Ontology
summary: The set of a vault's schemas taken together - its types and the typed relations between them.
related:
  - "[Schema](schema.md)"
  - "[Relation](relation.md)"
---
# Ontology

Knott borrows vocabulary from RDF (entity, attribute, relation/predicate, schema) but does not implement RDF. A vault's ontology is simply its schema files: small enough to understand by reading a few YAML files.

## This docs folder is an example

`docs/` is itself a Knott vault. Its ontology:

```
            ┌──────────── related ───────────┐
            ▼                                │
guide ── concepts ──▶ concept ◀──────────────┘
  │                      ▲  ▲
  └── commands ─▶ command ┘  │ (concepts)
                             │
issue_code ─── about ────────┤
decision ──── affects ───────┘
decision ── supersedes ──▶ decision
```

| Type | Holds | Key relations |
|---|---|---|
| `concept` | the model's core ideas | `related → concept` |
| `command` | CLI commands | `concepts → concept` |
| `issue_code` | every validation code, cause and fix | `about → concept` (required) |
| `guide` | how-tos | `concepts → concept`, `commands → command` |
| `decision` | design records | `affects → concept` (required), `supersedes → decision` |

Run `knott types --verbose` inside `docs/` to see them, and `knott validate` to check the whole folder.

## Designing your own

- Start with 2–4 types. Add one when you find yourself writing the same frontmatter keys repeatedly.
- Point relations from the thing that *knows* about the other: a transcript knows its script, not the reverse.
- Use `required: true` sparingly. It's for things that make the entity meaningless when missing.
- Write a `description` on every type and relation. Agents read them.
