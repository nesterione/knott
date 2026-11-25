---
type: issue_code
code: entity-abstract-type
stage: entity
about: "[Schema](../concepts/schema.md)"
---
# `entity-abstract-type`

The entity's `type` is a concept marked `abstract: true`. An abstract type exists to share properties and to be a reference target; no entity can have it.

## Example

```yaml
# concept: name: concept, abstract: true; `tool` and `person` extend it
type: concept
title: Zettelkasten
```

## Fix

Change `type` to the subtype that fits; the message lists the concrete ones. Do not remove `abstract` from the concept to make the entity pass.

## Notes

Reported at the line of `type`. The entity's properties are still checked against the abstract concept, and references to it still resolve.
