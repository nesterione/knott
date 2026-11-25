---
type: issue_code
code: entity-misplaced
stage: entity
about: "[Schema](../concepts/schema.md)"
---
# `entity-misplaced`

The entity's type declares `path`, and the entity's folder matches none of its patterns.

## Example

```yaml
# concept: name: episode, path: episodes/*
# file: notes/episode-42.md
type: episode
```

## Fix

Move the file into a folder the message names, then fix the links the move breaks: run `knott refs <file>` before moving to see who points at it, and `knott validate` after. If the file is where it should be, widen `path` in the concept file (`episodes/**` allows subfolders).

## Notes

Reported at the line of `type`, with no field. Only the folder is compared, with regard to case; the vault root is shown as `.`. A path given to `knott validate` is taken as written, so pass it in the case it has on disk. The entity's other checks still run.
