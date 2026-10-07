---
type: guide
title: Writing schemas
audience: human
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Attribute](../concepts/attribute.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Ontology](../concepts/ontology.md)"
commands:
  - "[knott types](../commands/types.md)"
  - "[knott validate](../commands/validate.md)"
---
# Writing schemas

## A good schema

```yaml
type: decision
description: >
  An architecture decision record: a choice made where the spec was silent
  or ambiguous, and why.
attributes:
  title:
    type: string
    required: true
  decided_on:
    type: date
    required: true
relations:
  affects:
    target: concept
    required: true
    description: Concepts whose behavior the decision shapes.
  supersedes:
    target: decision
```

This is the real schema from this folder (`.knott/schemas/decision.yaml`).

## Checklist

- **Name types as singular nouns**: `transcript`, not `transcripts`. Lowercase, `-` or `_` allowed.
- **Describe everything.** An agent creating an entity reads the schema first; the `description` is its only guidance on intent.
- **Require only what's essential.** Every `required: true` is friction for every future entity.
- **Choose the relation's direction carefully.** It lives on the source and is never duplicated on the target. Put it on the side that is created later or knows about the other.
- **Self-reference is fine**: `supersedes: {target: decision}`.
- **Prefer a relation over a string attribute** when the value names another entity. You get existence and type checks for free.
- **Don't fight strict typing.** If a value may be `"N/A"`, it's a `string`, not an `integer`.

## Iterating

Schemas are validated on every run, before entities. After editing one:

```sh
knott types --verbose   # did it load?
knott validate          # did existing entities break?
```

Schemas have no version field; Git holds their history.
