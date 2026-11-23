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

A type is one Markdown file in `.knott/concepts/`. The frontmatter is the schema. The body is a template for entities of that type.

## A good concept file

```markdown
---
name: decision
description: >
  An architecture decision record: a choice made where the spec was silent or ambiguous, and why.
properties:
  title:
    type: string
    required: true
  decided_on:
    type: date
    required: true
  affects:
    type: list
    required: true
    description: Concepts whose behavior the decision shapes.
    items:
      type: reference
      target: concept
  supersedes:
    type: reference
    target: decision
---
# <!-- "NNNN: <the decision as a sentence>", the same text as the `title` property. -->

**Context.**

<!-- What problem or gap forced a choice. -->

**Decision.**

<!-- What was decided. -->
```

This is a shortened copy of this folder's `.knott/concepts/decision.md`.

## Checklist

- **Name types as singular nouns**: `transcript`, not `transcripts`. Lowercase, `-` or `_` allowed.
- **Describe everything.** An agent creating an entity reads the concept file first; the `description` is its only guidance on intent.
- **Require only what's essential.** Every `required: true` is friction for every future entity.
- **Choose the reference's direction carefully.** It lives on the source and is never duplicated on the target. Put it on the side that is created later or knows about the other.
- **Self-reference is fine**: `supersedes: {type: reference, target: decision}`.
- **One or several?** `type: reference` holds exactly one. If an entity can point at several, declare a `list` of references from the start; a single value is then written as a one-item list.
- **Several possible types?** Use `target: [episode, meeting]` rather than two properties.
- **Prefer a reference over a string** when the value names another entity. You get existence and type checks for free.
- **Require a `kid` when outside tools track entities**: `kid: required` at the top level. Progress records and logs can then refer to the entity even after its file moves. See [Kid](../concepts/kid.md).
- **Don't fight strict typing.** If a value may be `"N/A"`, it's a `string`, not an `integer`.

## Structured properties

When a value has parts, declare them instead of leaving the key undeclared. A `lexeme` in a language-learning vault:

```yaml
name: lexeme
description: A word with its senses and forms.
properties:
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
        see_also: {type: reference, target: lexeme}
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
  - id: friend
    ru: друг
    see_also: "[Bičiulis](biciulis.md)"
forms:
  sg: {nom: draũgas, gen: draũgo, acc: draũgą}
```

- **`object` when you know the keys, `map` when you don't.** Objects are closed, so a typo such as `rus:` is reported. Map keys are free strings.
- **`required: true` on a list means "at least one item".** Items and map values can never be empty, so `required` isn't allowed on `items` or `values`.
- **Describe `items` too.** "One sense per meaning" tells an agent what one item stands for.
- **References can sit inside.** `senses[0].see_also` is checked like a top-level reference, and problems name that path.

See [Attribute](../concepts/attribute.md) and [Relation](../concepts/relation.md) for the full rules.

## Templates

Write the body once the entities of a type share a structure. Use the real headings, and put a `<!-- … -->` comment under each saying what goes there:

```markdown
## Example

<!-- A minimal fenced block that triggers the code. -->

## Fix

<!-- What to change, or the command to run. -->
```

- **Headings are structure.** Write them as they should appear in the entity. When a heading's text varies, like the H1, write the heading with a comment as its text: `# <!-- The episode title. -->`.
- **No placeholders.** There is no `{{…}}` syntax. Knott stores the body as written and never checks entities against it.
- **Mark optional sections** in their comment ("Delete this section if there is nothing to add").

## Iterating

Concept files are validated on every run, before entities. After editing one:

```sh
knott types --verbose   # did it load, with the shapes and references you meant?
knott validate          # did existing entities break?
```

Concept files have no version field; Git holds their history.
