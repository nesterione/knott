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

## Structured attributes

When a value has parts, declare them instead of leaving the key undeclared. A `lexeme` in a language-learning vault:

```yaml
type: lexeme
description: A word with its senses and forms.
attributes:
  lemma:
    type: string
    required: true
  tags:
    type: list
    items: {type: string}
  senses:
    type: list
    required: true
    items:
      type: object
      description: One sense per meaning.
      fields:
        id: {type: string, required: true}
        ru: {type: string, required: true, description: Russian gloss}
  forms:
    type: map
    description: Inflection table, by number and then by case.
    values:
      type: map
      values: {type: string}
```

```yaml
# an entity of that type
type: lexeme
lemma: draugas
tags: [noun, a1]
senses:
  - {id: friend, ru: друг}
forms:
  sg: {nom: draũgas, gen: draũgo, acc: draũgą}
```

- **`object` when you know the keys, `map` when you don't.** Objects are closed, so a typo such as `rus:` is reported. Map keys are free strings.
- **`required: true` on a list means "at least one item".** Items and map values can never be empty, so `required` isn't allowed on `items` or `values`.
- **Describe `items` too.** "One sense per meaning" tells an agent what one item stands for.
- **Keep references as relations.** Structured values can't contain relations yet. A value that names another entity belongs in a top-level relation.

See [Attribute](../concepts/attribute.md) for the full rules.

## Iterating

Schemas are validated on every run, before entities. After editing one:

```sh
knott types --verbose   # did it load, with the shapes you meant?
knott validate          # did existing entities break?
```

Schemas have no version field; Git holds their history.
