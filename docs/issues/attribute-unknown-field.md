---
type: issue_code
code: attribute-unknown-field
stage: attribute
about: "[Attribute](../concepts/attribute.md)"
---
# `attribute-unknown-field`

A value inside an `object` attribute has a key that the object's `fields` don't declare. Objects are closed, so a misspelled nested key doesn't slip through ([decision 0008](../decisions/0008-structured-attributes.md)).

## Example

```yaml
# schema: senses is a list of objects with fields id and ru
senses:
  - id: home
    rus: дом      # unknown field `rus`; did you mean `ru`?
```

## Fix

Rename the key to one of the allowed fields the message lists. If the key is legitimate, declare it in the schema's `fields`. If the keys are meant to be free-form, declare the attribute as a `map` instead of an `object`.

## Notes

Only declared objects are closed. Top-level frontmatter keys that the schema doesn't declare are still allowed and unchecked.
