---
type: intent
title: File properties
status: open
raised_on: 2026-11-24
concepts:
  - "[Attribute](../concepts/attribute.md)"
  - "[Entity](../concepts/entity.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
---
# File properties

## Need

Some knowledge is not Markdown: a recording is an mp3, a dataset is a JSON file, a contract is a PDF, a diagram is an image. Today an entity can only mention such a file in an undeclared key, which knott never checks, because a reference accepts `.md` targets only. So a vault can't say "every recording has an audio file", a moved or deleted file goes unnoticed, and nothing tells an agent which key holds the file. Some of these files are too large or too private for the repository and are kept in another store, such as Google Drive, and the entity still needs to name them.

## Example

A podcast vault:

- `recordings/episode-42.md` is a `recording`. Its `audio` must point at an mp3 or wav file. `knott validate` reports a missing file, a wrong extension, or a path that leaves the vault.
- Its `cover` is an image in the vault, at `img/episode-42.png`.
- Its `slides` is a PDF kept in the team's Google Drive, not in the repository. The value is a URI such as `gdrive:1AbCdEf`. Knott checks that its scheme is a connector the vault declares and never fetches the file.
- Its `images` is a list. Two items are files in the vault and one is in Google Drive. Each item is checked by its own rule.

## Direction

Agreed on 2026-11-24, for the spec to build on:

- The Markdown file stays the entity. A file is a value of a new property shape, `file`, next to `reference`. Knott ships no built-in attachment type; a vault that wants a generic `attachment` concept defines one with a required `file` property.
- Knott checks that a file is there, not what is in it.
- A file kept outside the vault is written as a URI, such as `s3://talks/ep42.pdf` or `gdrive:1AbCdEf`, as `kid:<uuid>` is for references. Its scheme is a connector declared in the vault, so knott can report an unknown one.
- `file` nests like `reference`: in a list, a map or an object field. Each item of a list is resolved on its own, so one list can mix files in the vault with files behind different connectors.

## Open questions

Answered by [spec 0008](../specs/0008-file-properties.md). Left for a later spec:

- Whether a file in the vault that no entity points at is reported.
- Whether `knott refs` accepts a file path and lists the entities that point at it.
