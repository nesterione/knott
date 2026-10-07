---
type: concept
title: Schema
summary: A YAML file in `.knott/schemas/` that defines one entity type, its attributes, and its relations.
spec_section: "§4, §7"
related:
  - "[Attribute](attribute.md)"
  - "[Relation](relation.md)"
  - "[Ontology](ontology.md)"
---
# Schema

```yaml
type: transcript
description: >
  Transcript of recorded spoken content.
attributes:
  title:
    type: string
    required: true
    description: Human-readable title.
relations:
  derived_from:
    target: script
    description: The script this transcript was produced from.
```

## Discovery

Every `.knott/schemas/**/*.yaml` file is a schema (`.yml` is not recognized). Subfolders are only for your organization: the type's identity is the value of `type`, not the filename.

## Allowed keys

| Level | Key | Required | Notes |
|---|---|---|---|
| top | `type` | yes | `^[a-z][a-z0-9_-]*$` |
| top | `description` | no | string |
| top | `attributes` | no | field name → attribute definition |
| top | `relations` | no | field name → relation definition |
| attribute | `type` | yes | `string`, `integer`, `number`, `boolean`, `date`, `datetime` |
| attribute | `required` | no | `true`/`false`, default `false` |
| attribute | `description` | no | string |
| relation | `target` | yes | an existing type (self-reference allowed) |
| relation | `required` | no | `true`/`false`, default `false` |
| relation | `description` | no | string |

Unknown keys are **errors** in schemas (Knott owns these files, so `atributes:` must not pass silently), unlike in entities.

A field cannot be named `type`, and cannot be both an attribute and a relation.

## Three readers

A schema is a validation contract, documentation for humans, and the context an AI agent reads before writing an entity. Write `description`s for all three.
