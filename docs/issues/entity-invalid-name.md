---
type: issue_code
code: entity-invalid-name
stage: entity
about: "[Schema](../concepts/schema.md)"
---
# `entity-invalid-name`

The entity's type declares `filename`, and the file's name does not match the pattern.

## Example

```yaml
# concept: name: spec, filename: { pattern: "{number}-{slug}", parts: { number: { match: "[0-9]{4}" }, slug: } }
# file: specs/loops.md
type: spec
```

## Fix

Rename the file so it fits the pattern in the message; `knott types --verbose` shows how to fill each part. Run `knott refs <file>` before renaming to see who points at it, and `knott validate` after. If the name is right, change `filename` in the concept file.

## Notes

Reported at the line of `type`, with no field. Only the name is compared, without `.md` and with regard to case; the folder belongs to [`entity-misplaced`](entity-misplaced.md). The message lists the expression of each part that has one.
