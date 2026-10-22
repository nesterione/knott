---
type: issue_code
code: kid-missing
stage: kid
about: "[Kid](../concepts/kid.md)"
---
# `kid-missing`

The entity's schema says `kid: required`, but the entity has no `kid`, or an empty one.

## Example

```yaml
# schema: type: lexeme, kid: required
type: lexeme
lemma: namas
```

## Fix

Run `knott validate --fix <file>`. It inserts a new `kid` after the `type:` line. If the file has an empty `kid:` line, delete it first; `--fix` only adds a `kid` when the key is absent.

## Notes

The issue points at the `kid:` line when there is one, otherwise at the `type:` line.
