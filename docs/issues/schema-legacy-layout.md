---
type: issue_code
code: schema-legacy-layout
stage: schema
about: "[Schema](../concepts/schema.md)"
---
# `schema-legacy-layout`

The vault still has a `.knott/schemas/` folder, the schema layout used before 0.5. Knott now reads types only from concept files in `.knott/concepts/` ([decision 0010](../decisions/0010-concept-files-and-reference-properties.md)).

## Example

```
✗ .knott/schemas
  `.knott/schemas/` is the pre-0.5 schema layout; knott now reads concept files from `.knott/concepts/` (decision 0010)
  run `knott migrate` to convert the schemas, then review the diff
```

## Fix

Run [`knott migrate`](../commands/migrate.md). It writes one concept file per YAML schema, deletes `.knott/schemas/`, and validates the vault. Review the diff in Git before you commit.

## Notes

While the folder exists, this is the only issue a run reports: no concept files are loaded and no entities are checked, so every entity doesn't also report `entity-unknown-type`. `knott types` prints no types, and `knott view` exits `2` with no types to show. The issue has no line or field.
