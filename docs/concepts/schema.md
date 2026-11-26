---
type: concept
title: Schema
summary: The frontmatter of a concept file in `.knott/concepts/`, which defines one entity type and its properties.
spec_section: "§4, §7"
related:
  - "[Attribute](attribute.md)"
  - "[Relation](relation.md)"
  - "[Ontology](ontology.md)"
---
# Schema

Each type is defined by one **concept file**, a Markdown file in `.knott/concepts/`. Its frontmatter is the type's **schema**. Its body is an optional **template** for the body of entities of that type.

```markdown
---
name: transcript
description: Transcript of recorded spoken content.
properties:
  title:        { type: string, required: true }
  derived_from: { type: reference, target: script }
  speakers:
    type: list
    items:
      type: object
      fields:
        person: { type: reference, target: person }
        role:   { type: string }
---
# Transcript

<!-- One paragraph: who speaks and what it covers. -->
```

## Discovery

Every `.knott/concepts/**/*.md` file is a concept file. Subfolders are only for your organization: the type's identity is the value of `name`, not the filename. Two files with the same `name` are an error that names both.

Concept files use `name:`, not `type:`. Entities keep `type: transcript`, so a concept file is never mistaken for an entity.

## Allowed keys

| Level | Key | Required | Notes |
|---|---|---|---|
| top | `name` | yes | `^[a-z][a-z0-9_-]*$` |
| top | `description` | no | string |
| top | `extends` | no | the name of one other concept, this type's parent, see [Inheritance](#inheritance) |
| top | `abstract` | no | `true`: no entity may have this type |
| top | `kid` | no | `required`: every entity needs a [kid](kid.md) |
| top | `path` | no | the folders entities of this type are stored in: `path: specs`, or a list, see [Where entities live](#where-entities-live) |
| top | `filename` | no | how entity files of this type are named, see [File names](#file-names) |
| top | `properties` | no | property name → definition, in the order you want them shown |
| property | `type` | yes | a scalar type, `enum`, `list`, `object`, `map`, `reference` or `file` |
| property | `required` | no | `true`/`false`, default `false` |
| property | `description` | no | string |
| property | `items` / `fields` / `values` | with `list` / `object` / `map` | see [Attribute](attribute.md) |
| property | `target` | with `reference` | a type name, a list of type names (`target: [episode, meeting]`), or `any` for an [open reference](relation.md#open-references) |
| property | `options` | with `enum` | the allowed values: `options: [m, f]`, or option → description, see [Attribute](attribute.md#enums) |
| property | `accept` | no, `file` only | the extensions a vault file may have: `accept: [mp3, wav]`, see [File](file.md) |
| property | `relation` | no, `reference` only | a relation defined in `.knott/relations/`, see [relation definitions](relation.md#relation-definitions) |

Unknown keys are **errors** in concept files (Knott owns these files, so `propertes:` must not pass silently), unlike in entities. A top-level property can't be named `type` or `kid`; both belong to knott.

A property whose shape is `reference` is a [relation](relation.md). Every other property is an [attribute](attribute.md). Both live in the one `properties` map. A concept cannot be named `any`: the word is reserved for `target: any`.

## Inheritance

A concept can extend one other concept. The child is a kind of the parent: it has the parent's properties, and a reference that targets the parent accepts it.

```yaml
# .knott/concepts/concept.md
name: concept
abstract: true
properties:
  title: { type: string, required: true }
  related:
    type: list
    items: { type: reference, target: concept }
```

```yaml
# .knott/concepts/tool.md
name: tool
extends: concept
properties:
  homepage: { type: string }
  made_by:  { type: reference, target: organization }
```

- **One parent**, any depth. An entity writes its own type (`type: tool`) and never names the parent.
- **Inherited**: every property, with all its keys, root ancestor first; the body template when the child's body is empty; `path` and `filename` when the child declares none; `kid: required`, which a child cannot turn off. `description` and `abstract` are not inherited.
- **A child only adds properties.** Repeating one an ancestor declares is [`schema-property-redefined`](../issues/schema-property-redefined.md), and the inherited definition stands. If a child needs a property different, it belongs on the children.
- **`abstract: true`** marks a type that exists to share properties and to be a target. An entity with that type is [`entity-abstract-type`](../issues/entity-abstract-type.md). An abstract parent is also how you name a group of types: `target: page` accepts every subtype of `page`.
- **A reference accepts subtypes**: `target: concept` takes a `tool`; `target: tool` does not take a plain `concept`.
- **Errors**: a parent no concept defines is [`schema-unknown-parent`](../issues/schema-unknown-parent.md), a loop of parents is [`schema-extends-cycle`](../issues/schema-extends-cycle.md). The concept then loads as a root type.

An issue on an inherited property ends with the file that declares it: ``declared in .knott/concepts/concept.md (`tool` extends `concept`)``. `knott types --verbose` shows inherited properties in their own `properties (from concept):` block and marks an inherited template, `path`, `filename` or `kid` with `(from concept)`.

## Where entities live

Without `path`, an entity of the type can be stored anywhere in the vault. With it, an entity in any other folder is [`entity-misplaced`](../issues/entity-misplaced.md):

```yaml
name: episode
path: episodes/*        # or a list: [specs, drafts/**]
```

A pattern is matched against the entity's folder, relative to the vault root; the file name is not part of it. Matching regards case.

| Pattern | Matches |
|---|---|
| `specs` | the folder `specs` only, not its subfolders |
| `episodes/*` | any folder directly in `episodes`. `*` is any run of characters inside one folder name, also none: `drafts-*` |
| `episodes/**` | `episodes` and every folder below it |
| `"**/specs"` | a folder named `specs` at any depth |
| `.` | the vault root |

Nothing else is special: no `?`, `[…]` or regular expressions. Quote a pattern that starts with `*` (`path: "**/specs"`), or YAML reads it as an alias. `path` says where a type lives, not what a folder holds, so other types and plain notes can share the folder. Knott never moves a file: references are relative paths, so a move changes the links around it.

## File names

Without `filename`, an entity file can have any name. With it, a name that does not fit is [`entity-invalid-name`](../issues/entity-invalid-name.md):

```yaml
name: spec
filename:
  pattern: "{number}-{slug}"
  parts:
    number:
      match: "[0-9]{4}"
      description: The next free number in specs/.
    slug:
      match: "[a-z0-9]+(-[a-z0-9]+)*"
      description: What the change does, in two to five lowercase words.
```

- **`pattern`** is the file name without `.md`: literal text and `{part}` placeholders. Literal text is matched exactly, so `.` and `(` need no escaping. A part is used once; a pattern with no parts is a fixed name.
- **`parts`** defines every part of the pattern. Both keys are optional, and a part can be left empty (`slug:`).
- **`match`** is a regular expression (Python `re` syntax) the part must match in full. Without it, the part is any non-empty text.
- **`description`** tells whoever names the file how to fill the part: where the value comes from, how long, in what form. Knott shows it in `knott types --verbose` and never interprets it. For an agent it works as the prompt for that part.

Quote `pattern` and `match`: YAML reads an unquoted leading `{` as a mapping and `[` as a list.

Knott checks that the whole name can be split into the literal text and the parts. It does not extract the parts, compare them with properties, or pick a name itself. Matching regards case. Renaming a file changes the links that point at it, so run [`knott refs`](../commands/refs.md) first.

## The template

The body is stored as written. Knott never checks an entity's body against it. Agents copy it when they start a new entity, so write the body's sections as real headings and explain each one in a `<!-- … -->` comment:

```markdown
# <!-- The episode title. -->

<!-- One paragraph: who speaks and what it covers. -->

## Highlights

<!-- Three to five bullets, each with a timestamp. -->
```

There is no placeholder syntax. Comments stay out of Obsidian's reading view, and the agent deletes them once a section is filled. `knott types --verbose` shows `template: yes` for a type that has one. An empty body means no template.

## Upgrading from `.knott/schemas/`

Before 0.5, a type was a YAML file in `.knott/schemas/` with separate `attributes` and `relations` maps. A vault that still has that folder reports only [`schema-legacy-layout`](../issues/schema-legacy-layout.md). Run [`knott migrate`](../commands/migrate.md) to convert it. See [decision 0010](../decisions/0010-concept-files-and-reference-properties.md).

## Three readers

A schema is a validation contract, documentation for humans, and the context an AI agent reads before writing an entity. Write `description`s for all three.
