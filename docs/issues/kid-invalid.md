---
type: issue_code
code: kid-invalid
stage: kid
about: "[Kid](../concepts/kid.md)"
---
# `kid-invalid`

The entity's `kid` is not a canonical lowercase UUID.

## Example

```yaml
kid: 3F2B8C1E-9D4A-4C2E-B7F1-0A6D5E9C8B21   # uppercase
kid: "{3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21}"  # braces
kid: draugas                                 # not a UUID
```

## Fix

When the value is a UUID in another spelling, the message gives the canonical form; write that. Otherwise, delete the line and run `knott validate --fix` to get a new one. If other entities refer to the old value with `kid:`, update them too.

## Notes

This is checked on every entity, whether or not its schema requires a `kid`. Only one spelling is accepted, so one entity can't hide behind two.
