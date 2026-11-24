---
type: issue_code
code: file-unknown-connector
stage: file
about: "[File](../concepts/file.md)"
---
# `file-unknown-connector`

The value starts with a scheme, so it is a URI, and no connector file in `.knott/connectors/` has that name. The message lists the declared connectors and suggests the closest.

## Example

```yaml
slides: gdrv:1AbCdEf                             # only `gdrive` is declared
video: https://drive.google.com/file/d/1AbCdEf   # no connector named `https`
data: a:b.json                                   # a file name with a colon
```

## Fix

- Fix the scheme if it is a typo.
- For a new store, add `.knott/connectors/<scheme>.md` with `name: <scheme>` and a description of what follows the scheme.
- For a file in the vault whose name has a colon, write `./a:b.json`.

## Notes

Schemes match without regard to case. Knott never contacts the store.
