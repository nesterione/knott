---
type: concept
title: Ontology
summary: The set of a vault's concept files taken together - its types and the typed relations between them.
related:
  - "[Schema](schema.md)"
  - "[Relation](relation.md)"
---
# Ontology

Knott borrows vocabulary from RDF (entity, attribute, relation/predicate, schema) but does not implement RDF. A vault's ontology is simply its concept files in `.knott/concepts/`, plus the [relation definitions](relation.md#relation-definitions) in `.knott/relations/` that say what its links mean: small enough to understand by reading a few of them.

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
decision ── supersedes, amends ──▶ decision
spec ── realizes ──▶ intent ── concepts ──▶ concept
spec ── decisions ──▶ decision
spec ── concepts ──▶ concept
spec ── supersedes, amends ──▶ spec
```

| Type         | Holds                                | Key relations                                           |
| ------------ | ------------------------------------ | ------------------------------------------------------- |
| `concept`    | the model's core ideas               | `related → concept`                                     |
| `command`    | CLI commands                         | `concepts → concept`                                    |
| `issue_code` | every validation code, cause and fix | `about → concept` (required)                            |
| `guide`      | how-tos                              | `concepts → concept`, `commands → command`              |
| `decision`   | design records: the choice and why   | `affects → concept` (required), `supersedes`/`amends → decision` |
| `spec`       | the exact behaviour of one change, frozen once implemented | `realizes → intent`, `decisions → decision`, `concepts → concept`, `supersedes`/`amends → spec` |
| `intent`     | wanted but not yet specified         | `concepts → concept`                                    |

Four relation files give those links a meaning:

| Relation     | Keys                                  | Named by                                 |
| ------------ | ------------------------------------- | ---------------------------------------- |
| `about`      | `inverse: discussed_in`               | `decision.affects`, `issue_code.about`   |
| `related`    | `symmetric`                           | `concept.related`                        |
| `supersedes` | `inverse: superseded_by`, `acyclic`   | `decision.supersedes`, `spec.supersedes` |
| `amends`     | `inverse: amended_by`, `acyclic`      | `decision.amends`, `spec.amends`         |

`knott refs specs/0005-concept-files.md` lists `specs/0006-relation-definitions.md` under `amended_by`, although 0005 is never edited.

Every type also has a body template, so a new page starts with the sections its siblings use. Run `knott types --verbose` inside `docs/` to see them and the relations, and `knott validate` to check the whole folder.

Run `knott view` inside `docs/` to explore it interactively.

## Designing your own

- Start with 2–4 types. Add one when you find yourself writing the same frontmatter keys repeatedly.
- Point relations from the thing that *knows* about the other: a transcript knows its script, not the reverse.
- When several properties mean the same link, or the link needs a name from the target side, add a relation file and name it with `relation:`.
- Use `required: true` sparingly. It's for things that make the entity meaningless when missing.
- Write a `description` on every type and property. Agents read them.
- Give a type a body template once its entities share sections. Agents copy it.
