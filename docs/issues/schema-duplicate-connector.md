---
type: issue_code
code: schema-duplicate-connector
stage: schema
about: "[File](../concepts/file.md)"
---
# `schema-duplicate-connector`

Two connector files in `.knott/connectors/` have the same `name`. The message names both files.

## Example

```
✗ .knott/connectors/s3.md:2  name
  connector `s3` is defined twice: in `.knott/connectors/cloud/bucket.md` and in `.knott/connectors/s3.md`
  each connector must be defined by exactly one connector file
```

## Fix

Delete one, or change its `name`. A connector's identity is the `name` value, not the filename.

## Notes

The first file by sorted path wins and stays loaded; the issue is reported on the later one.
