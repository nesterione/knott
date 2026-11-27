---
type: spec
title: "0017: Show the details of one type"
status: implemented
created_on: 2026-11-26
released_in: "0.14.0"
realizes:
  - "[Read the vault as data](../intents/read-the-vault-as-data.md)"
decisions:
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Ontology](../concepts/ontology.md)"
amends:
  - "[0015](0015-type-tree.md)"
---
# 0017: Show the details of one type

## Summary

`knott types NAME` prints everything needed to write one entity of that type: its `--verbose` block, its body template, and only the relations, connectors and loops that type uses. Today the only detailed view is `knott types --verbose` for the whole ontology, and the template needs a second read of the concept file. `knott types` without a name is unchanged.

## Behaviour

### Selecting types

- `knott types NAME...` takes one or more type names. Each must be a type a concept file defines; an abstract type is allowed.
- A name no concept defines is a usage error that lists the known types. Nothing is printed for the other names.
- A name given twice is printed once. Types are printed in the order given.
- With a name, the output is always detailed; `--verbose` is accepted and changes nothing.
- A name cannot be combined with `--tree` ([0015](0015-type-tree.md)): the tree is the whole ontology. It is a usage error.

### What is printed for a type

1. The type's block, exactly as `knott types --verbose` prints it: the header line, description, `extends`, `abstract`, `subtypes`, `kid`, `template: yes|no`, `path`, `filename` with its parts, `references`, the `properties (from <type>)` blocks and `properties`.
2. When the type has a template, own or inherited, a `template body:` line indented by two spaces, then the template verbatim, each line indented by four spaces (blank lines kept empty).

Types are separated by a blank line.

### Relations, connectors and loops

After the types, the same sections `--verbose` prints, limited to what the selected types use:

| Section | Included |
|---|---|
| `relations:` | the relations named by a reference property, own or inherited, at any depth, of a selected type |
| `connectors:` | every connector, when a selected type has a `file` property at any depth; otherwise none |
| `loops:` | the loops whose `type` is a selected type or one of its ancestors |

- Each entry is formatted as in `--verbose`, and entries keep its order (by name). A section with no entry is left out.
- A relation that only points *at* the type (named by another type's property) is not included: it is not something to write on this entity.
- Connectors are not narrowed by scheme, because a `file` property accepts any declared connector.

## CLI and API

```
knott types [NAME...] [--verbose] [--tree]
```

```
$ knott types intent
intent  (.knott/concepts/intent.md)
  Something we want knott to do but have not specified yet: …
  template: yes
  path: intents
  references: concepts[]
  properties:
    title*        string
    status*       string                       open or dropped. …
    raised_on*    date
    github_issue  integer                      The GitHub issue where it is discussed, if any.
    concepts      list of reference → concept  Concepts the intent would change.
  template body:
    # <!-- The intent as a short phrase, the same text as `title`. -->

    ## Need

    <!-- Who needs what, and what they do today without it. No solution yet. -->
    …
```

`intent` names no relation, has no `file` property and no loop follows it, so no section comes after it. `knott types spec` ends with a `relations:` section holding `amends` and `supersedes`, and a `loops:` section holding the `spec` loop.

- Exit codes are those of `knott types`: `0` on success; `1` when any concept, relation, connector or loop file has issues (all schema issues go to stderr, as today, after the output); `2` for no vault or an unknown `NAME`:

  ```
  $ knott types intnet
  error: no type named `intnet` (known types: `command`, `concept`, `decision`, `guide`, `intent`, `issue_code`, `spec`)
  ```
- No Python API change: `Knott.ontology()` already holds the types with their templates, and the relations, connectors and loops.

### The bundled skill

Step 1 of the skill's workflow stays `knott types --tree`, the overview. Step 2 becomes: run `knott types NAME` for the type you will write; it also prints the template, so the concept file need not be opened. This replaces the advice of [0015](0015-type-tree.md) to read the type in `knott types --verbose` before writing an entity. `knott types --verbose` stays documented as the way to read the whole ontology, for choosing between types and for writing concept files. The agent-workflow guide changes the same way.

## Edge cases

| Case | Result |
|---|---|
| `knott types tool`, where `tool` extends `concept` and `concept` has the template | the template is printed; the `template:` line reads `yes (from concept)` |
| `knott types concept`, where `concept` is abstract | printed, with `abstract: yes` and `subtypes:`; subtypes are not expanded |
| `knott types tool`, and a loop follows `concept.status` | the loop is included |
| `knott types concept`, and a loop follows `tool.status` | the loop is not included |
| A property names a relation no relation file defines | nothing is added to `relations:`; `relation-unknown` goes to stderr, exit 1 |
| `knott types spec intent` | both blocks, then one `relations:` and one `loops:` section for the two |
| `knott types spec nope` | exit 2; nothing printed for `spec` |
| `knott types spec --tree` | exit 2: a name cannot be combined with `--tree` |
| A template whose lines end in spaces | printed as is after the indent; blank lines get no indent |
| The vault has the legacy layout | as `knott types` today: the `schema-legacy-layout` issue, exit 1 |

## Out of scope

- `--format json` for `knott types`, with or without a name. The Python API has the data; a JSON form of the ontology is a separate change.
- Expanding subtypes of a selected type, or selecting by pattern.
- Printing the concept file's `description` of each property in full; it stays on one line, as in `--verbose`.
- Narrowing connectors by what a property accepts.

## Compatibility

Additive. `knott types`, `knott types --verbose` and `knott types --tree` print exactly what they did. Version 0.14.0, together with [0016](0016-list-and-show-entities.md).
