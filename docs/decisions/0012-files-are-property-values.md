---
type: decision
title: Files are values of a `file` property, and a URI names files kept elsewhere
status: accepted
decided_on: 2026-11-24
affects:
  - "[Entity](../concepts/entity.md)"
  - "[Attribute](../concepts/attribute.md)"
  - "[Schema](../concepts/schema.md)"
---
# 0012: Files are values of a `file` property, and a URI names files kept elsewhere

**Context.** Some knowledge is not Markdown: an mp3, a JSON file, a PDF, an image. An entity is a Markdown file ([0001](0001-markdown-is-source-of-truth.md)), and a reference accepts only `.md` targets, so such a file could only be mentioned in an undeclared key that knott never checks. Some of these files are also kept outside the repository, in a store such as S3 or Google Drive.

**Decision.**

1. **The Markdown file stays the entity.** A file is a value of a new property shape, `file`, which nests like `reference`. The key gives the file its meaning (`audio`, `cover`, `slides`).
2. **Knott ships no attachment type.** A vault that wants one defines a concept with a required `file` property.
3. **Knott checks that a file is there, not what is in it.** The one exception is the extension of a file in the vault, when the property lists the extensions it accepts.
4. **A file kept outside the vault is written as a URI**, such as `s3://talks/ep42.pdf` or `gdrive:1AbCdEf`. Its scheme is a connector, declared in `.knott/connectors/`, so an unknown scheme is reported. Knott reads nothing after the scheme and never fetches the file.
5. **Each value is resolved on its own.** One list can mix files in the vault with files behind different connectors.
6. **A URI is written on its own, never inside a Markdown link**, as `kid:` is in a reference.

**Not included.** Running a transfer: knott describes where a file is, and an agent skill or script moves it. Entities that are themselves copies of a remote page; see the [remote sources](../intents/remote-sources.md) intent.

**Why.**

- **A property, not a built-in type:** knott has no built-in types, and a fixed `attachment` schema could not be changed by its users. It would also need a way to point at the file, which is this property under another name.
- **Not "the file is the entity":** pairing a sidecar with a file by name changes what an entity is and what a reference accepts, breaks silently when the file is renamed, and lets one record describe only one file.
- **A URI, not an invented syntax:** `kid:<uuid>` already is one, and stores that have their own scheme (`s3://`, `gs://`) are written the way their own tools write them.
- **A declared scheme, not any web address:** a scheme the vault declares can be validated. An `https://` address says nothing about which store it is, has several forms for one file, and does not exist for every store. A vault that wants web addresses can still declare `https`.
- **A string, not an object value:** `reference` deliberately has one value shape, and an object is verbose in a list.
- **No list of allowed connectors per property:** nothing asked for it, and the vault's connector files already catch a mistyped scheme.

**Consequences.**

- A binary needs a small Markdown file beside it to be typed and linked.
- A file in the vault that no entity points at is invisible to knott.
- A URI is not clickable in Obsidian, and has no label. A caption is a field next to it.
- A file whose name contains a colon is written with a leading `./`.
- `.knott/` gains a third folder of definitions, `connectors/`.
