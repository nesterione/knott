---
type: concept
title: File
summary: A property of shape `file` names a file that is not treated as an entity, by a vault path or by a URI whose scheme is a connector the vault declares.
spec_section: "§8"
related:
  - "[Attribute](attribute.md)"
  - "[Reference resolution](reference-resolution.md)"
  - "[Schema](schema.md)"
---
# File

Some knowledge is not Markdown: an mp3, a JSON file, a PDF, an image. The Markdown file stays the entity, and a property of shape `file` names the other file. The value is one of two things:

- a **path**, for a file in the vault. Knott checks that the file exists.
- a **URI**, for a file kept somewhere else, such as `s3://talks/ep42.pdf` or `gdrive:1AbCdEf`. Knott checks only that its scheme is a connector the vault declares.

Knott never reads a file's content and never fetches anything.

```yaml
# .knott/concepts/recording.md
properties:
  audio: { type: file, required: true, accept: [mp3, wav] }
  slides: { type: file }
  images:
    type: list
    items: { type: file, accept: [png, jpg] }
```

```yaml
# recordings/episode-42.md
type: recording
audio: ../audio/episode-42.mp3
slides: s3://talks/episode-42.pdf
images:
  - ../img/episode-42-a.png
  - "[the whiteboard](../img/episode-42-b.jpg)"
  - gdrive:1AbCdEf
```

`file` nests like `reference`: in a list, a map or an object field. Each value is resolved on its own, so one list can mix vault files with files behind different connectors. Cardinality is strict: `type: file` holds exactly one file, and several is a `list` with `file` `items`.

A file property is an [attribute](attribute.md), not a [relation](relation.md): it draws no edge in `knott view`, and `knott refs` does not list it.

## `accept`

`accept` lists the extensions a vault file may have, lowercase and without the dot. The file's extension is the text after the last `.` of its name, compared without regard to case, so `TAKE.MP3` passes `accept: [mp3]`. **It is checked for paths only**: knott cannot see the file behind a URI.

## Paths

A path is written like a [reference](reference-resolution.md): relative to the file that contains it, plain or as a quoted Markdown link, with exact case. It must stay inside the vault and name a regular file. Any file passes, including a Markdown file or an entity; to point at an entity and check its type, use `reference`.

## URIs and connectors

Anything that starts with a scheme (`name:`) is a URI. A **connector** is a URI scheme the vault allows, with words about what it means. It is a Markdown file in `.knott/connectors/`:

```markdown
---
name: gdrive
description: The team's shared Google Drive. Written gdrive:<file id from the share link>.
---
<!-- Open as https://drive.google.com/file/d/<id>. Upload with the drive skill. -->
```

| Key | Required | Value |
|---|---|---|
| `name` | yes | a lowercase URI scheme, `^[a-z][a-z0-9+.-]*$`, and not `kid` |
| `description` | no | string |

- The body is guidance for people and agents: how to open a URI, which tool moves files. `knott types --verbose` prints it.
- A connector is identified by its `name`, not its file name. Subfolders only organise.
- A store with its own scheme is written the way its own tools write it (`s3://bucket/key`). A store without one gets a short scheme the vault names (`gdrive:<id>`).
- Knott reads nothing after the scheme. It may contain `#` and spaces; quote the value in YAML when it does. `S3://…` uses the connector `s3`.
- A URI is written on its own, never inside a Markdown link. A caption is a field next to it, in an object.
- A file whose own name has a colon is written with a leading `./`: `./a:b.json`.

Knott ships no connectors and moves no files. An agent skill or a script reads the URIs and does the transfer.

## Issues

[`file-missing`](../issues/file-missing.md) · [`file-invalid-value`](../issues/file-invalid-value.md) · [`file-unknown-connector`](../issues/file-unknown-connector.md) · [`file-outside-vault`](../issues/file-outside-vault.md) · [`file-not-found`](../issues/file-not-found.md) · [`file-extension-mismatch`](../issues/file-extension-mismatch.md) · [`schema-duplicate-connector`](../issues/schema-duplicate-connector.md)

Each value reports at most one issue: the first check that fails. See [decision 0012](../decisions/0012-files-are-property-values.md) and [spec 0008](../specs/0008-file-properties.md).
