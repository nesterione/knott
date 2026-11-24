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
  - "[knott refs](../commands/refs.md)"
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
    items: { type: reference, relation: about, target: concept }
  supersedes: { type: reference, relation: supersedes, target: decision }
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

## Files

When the knowledge is an mp3, a PDF, an image or a JSON file, keep the entity in Markdown and name the file in a [`file`](../concepts/file.md) property:

```yaml
properties:
  audio: { type: file, required: true, accept: [mp3, wav], description: The mixed take. }
  images:
    type: list
    items: { type: file, accept: [png, jpg] }
```

- **Name the property after what the file is** (`audio`, `cover`, `contract`), not `file` or `attachment`.
- **Use `accept` when a wrong file type would be a mistake.** It is checked for files in the vault only.
- **Declare a connector for each store outside the vault**, as `.knott/connectors/<scheme>.md`, and say in its description what follows the scheme. Values are then written `s3://bucket/key` or `gdrive:<id>`.
- **Put a caption in a field**, with a list of objects: `fields: { file: { type: file, required: true }, caption: { type: string } }`.
- **For a generic attachment type**, define a concept with one required `file` property. Knott ships none.

## Naming the link

A property's key says where a link is stored. A **relation file** says what the link means, once, for every property that uses it. Add one when several properties mean the same thing (`decision.affects` and `issue_code.about` both say "this is about that concept"), when the link needs a name from the target side, or when it must never loop. This folder's `.knott/relations/supersedes.md`:

```markdown
---
name: supersedes
inverse: superseded_by
acyclic: true
description: This entity replaces the target entirely. The target is kept unchanged as history.
---
Use `supersedes` when the old record is no longer the current answer: a new decision reverses an old one, or a new spec replaces an old spec as a whole. …

When the old record still stands and only part of it changes, use `amends`. …
```

A property names it with `relation:`, as in the `decision` example above.

- **`relation:` goes on the `reference`**, so for a list it goes on `items`, for a map on `values`. Write the reference on one line with `relation` straight after `type` (`items: { type: reference, relation: about, target: concept }`), so a defined link stands out from a plain one.
- **A plain reference is an inline relation**: unnamed, known only as `<type>.<property path>`. Give it a relation file when a second property means the same thing or it needs `inverse`, `symmetric` or `acyclic`.
- **Name the `inverse` from the target's side**: `superseded_by`, `discussed_in`. It is a label for [`knott refs`](../commands/refs.md), never a property, so it must not equal a top-level property of a concept the relation can point at.
- **`symmetric: true` for peers**, such as `related`. Store the link on one side; `knott refs` shows it from both. A symmetric relation has no `inverse` and isn't `acyclic`.
- **`acyclic: true` for anything that replaces or derives from something else.** A loop is reported as `relation-cycle`.
- **Write the body as guidance**: when to use this relation and which one to use instead. Agents read it in `knott types --verbose` before choosing a property.

See [Relation](../concepts/relation.md#relation-definitions) for the full rules.

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
knott types --verbose   # did it load, with the shapes, references and relations you meant?
knott validate          # did existing entities break?
```

Concept files have no version field; Git holds their history.
