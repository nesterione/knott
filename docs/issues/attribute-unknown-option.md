---
type: issue_code
code: attribute-unknown-option
stage: attribute
about: "[Attribute](../concepts/attribute.md)"
---
# `attribute-unknown-option`

The value of an `enum` property is a string that is not one of the options its concept lists. The message lists every option and, when one is close, suggests it.

## Example

```yaml
# concept: gender: { type: enum, options: [m, f] }
#          level:  { type: enum, options: [A1, A2, B1] }
gender: female
level: a1        # did you mean `A1`?
```

## Fix

Write one of the listed options, exactly as spelled. Options are case-sensitive and are not trimmed. `knott types --verbose` shows each property's options, with their descriptions.

## Notes

If the value is right and the set is incomplete, add the option to `options` in the concept file. A value that is not a string at all, such as an unquoted `no` or `1`, is [`attribute-type-mismatch`](attribute-type-mismatch.md); quote it.
