---
type: spec
title: "0008: File properties and connectors"
status: implemented
created_on: 2026-11-24
released_in: "0.7.0"
realizes:
  - "[File properties](../intents/file-properties.md)"
decisions:
  - "[0012](../decisions/0012-files-are-property-values.md)"
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
  - "[0006](../decisions/0006-symlinks-and-containment.md)"
  - "[0005](../decisions/0005-empty-values.md)"
concepts:
  - "[Attribute](../concepts/attribute.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Entity](../concepts/entity.md)"
  - "[Ontology](../concepts/ontology.md)"
amends:
  - "[0005](0005-concept-files.md)"
---
# 0008: File properties and connectors

## Summary

A concept can declare a property of shape `file`: a value that names a file without treating it as an entity, such as an mp3, a JSON file, a PDF or an image. The value is one of two things:

- a **path**, for a file in the vault. Knott checks that the file exists.
- a **URI**, for a file kept somewhere else, such as `s3://talks/ep42.pdf` or `gdrive:1AbCdEf`. Its scheme must be a connector the vault declares in `.knott/connectors/*.md`. Knott checks nothing else about it.

`file` nests like `reference`, so one list can mix both. Knott never reads a file's content and never fetches anything. The change is additive.

## Behaviour

### The `file` shape

```yaml
# .knott/concepts/recording.md
---
name: recording
properties:
  title: { type: string, required: true }
  audio: { type: file, required: true, accept: [mp3, wav] }
  slides: { type: file }
  images:
    type: list
    items: { type: file, accept: [png, jpg] }
---
```

```yaml
# recordings/episode-42.md
---
type: recording
title: Episode 42
audio: ../audio/episode-42.mp3
slides: s3://talks/episode-42.pdf
images:
  - ../img/episode-42-a.png
  - "[the whiteboard](../img/episode-42-b.jpg)"
  - gdrive:1AbCdEf
---
```

- `file` is allowed wherever a shape is: at the top level, as list `items`, as map `values`, or as an object field, at any depth.
- A `file` definition has one key of its own, besides `required` and `description`:

  | Key | Required | Value |
  |---|---|---|
  | `accept` | no | a non-empty list of unique extensions, each matching `^[a-z0-9]+$` (no dot). Absent: any extension, or none. **Checked for paths only**: knott cannot see the file behind a URI. |

- `accept` on any other shape is `schema-invalid-field` ("only allowed when `type` is file"); on a `list` or `map` the message says to put it on `items` or `values`. `target` and `relation` on a `file` are `schema-invalid-field`.
- A `file` property is an attribute, not a relation: it is not an edge in `knott view`, is not listed by `knott refs`, and does not count under "relations".

### Connector files

A connector is a URI scheme the vault allows, with words about what it means.

```yaml
# .knott/connectors/gdrive.md
---
name: gdrive
description: The team's shared Google Drive. Written gdrive:<file id from the share link>.
---
<!-- Open as https://drive.google.com/file/d/<id>. Upload with the drive skill. -->
```

- Discovered from `.knott/connectors/**/*.md`. Subfolders are only for organisation. Other file types are ignored. Connector files are loaded on every run, scoped or not.
- A connector is identified by its `name`, never by its file name.
- The body is optional guidance for people and agents (how to open a URI, which tool moves files), stored verbatim (`None` when blank) and shown by `types --verbose`. It is never checked against anything.
- Keys are closed:

  | Key | Required | Value |
  |---|---|---|
  | `name` | yes | a lowercase URI scheme: `^[a-z][a-z0-9+.-]*$`, and not `kid`. Connector names are their own namespace, separate from concepts and relations. |
  | `description` | no | string |

- A missing, invalid or reserved `name` is `schema-invalid-field`, and the file defines no connector.
- An invalid `description` is `schema-invalid-field`; the connector still loads, without it. Any other key is `schema-invalid-field` with a "did you mean" suggestion.
- A file with no frontmatter, frontmatter that isn't a mapping, or invalid YAML, is `schema-invalid-yaml`.
- Two files with the same `name` are `schema-duplicate-connector`, reported at the second file in path order and naming both. The first one defines the connector.
- A connector that no value uses is valid.

### Value shape

A shape **holds files** when it is `file`, or a list or map whose items are files, at any depth. Such a property follows the rules spec 0005 gives a shape that holds references, with `file-missing` in place of `relation-missing` and `file-invalid-value` in place of `relation-invalid-value`. Everything else keeps its `attribute-*` codes.

Cardinality is strict. `type: file` holds exactly one file. Several is `type: list` with `file` `items`.

| Value | `file` | `list` of `file` |
|---|---|---|
| `null` / `""` | absent | absent |
| `[]` | `file-invalid-value` | absent |
| `{}` | `file-invalid-value` | `file-invalid-value` |
| string | resolved | `file-invalid-value` ("write it as a list of files, even for one") |
| list | `file-invalid-value` ("declare `type: list` with file `items` for several") | each item resolved; a null or empty item is `file-invalid-value` |
| number, boolean, non-empty mapping | `file-invalid-value` | `file-invalid-value` |

- A value of the wrong kind is reported once, and its contents are not checked.
- A `required: true` property that holds files and is absent is `file-missing`.

### Resolving a value

Each string is resolved on its own, by the steps below, in order. **The first step that fails reports one issue, and the value is not checked further.**

`SCHEME` is `^[A-Za-z][A-Za-z0-9+.-]*:`, the same test references use today to reject a URL.

1. **Trim** whitespace around the string.
2. **Read the form.**
   - It starts with `[[`: `file-invalid-value` (wikilinks are not supported).
   - It is a Markdown link `[label](destination)`: take the destination, and remove a `<…>` wrapper if there is one. A destination with whitespace and no wrapper is `file-invalid-value`. A destination that matches `SCHEME` is `file-invalid-value` ("write a URI on its own, without a link"). Otherwise percent-decode the destination once. The result is a **path**.
   - It starts with `[` and is not a link: `file-invalid-value`.
   - It matches `SCHEME`: it is a **URI**.
   - Otherwise it is a **path**, taken literally, with no decoding.
3. **For a URI:**

   ```
   the scheme, lowercased, is not `kid`        → file-invalid-value
     ("`kid:` names an entity; use a `reference` property")
   something follows the first `:`             → file-invalid-value
   a connector has that name                   → file-unknown-connector
   ```

4. **For a path:**

   ```
   it is not empty, has no `#`, is not absolute → file-invalid-value
   it stays inside the vault root               → file-outside-vault
     (lexically, then by real path, as decision 0006 does for references)
   a file exists there, with exact case         → file-not-found
     (a folder gets the message "is a folder, not a file")
   its extension is in `accept`                 → file-extension-mismatch
   ```

Notes on the steps:

- **The form decides, and decoding never changes it.** A string with a scheme is always a URI, so `gdrive:` with its id deleted is an invalid URI, never a path. A file whose name has a colon is written with a leading `./`: `./a:b.json`. In a link, `[x](a%3Ab.json)` is the path `a:b.json`.
- **A link holds a path, never a URI**, as a link in a reference never holds `kid:`. A caption for a file kept elsewhere is a field next to it, in an object.
- **Decoding** applies to link destinations only and follows references: `%20` is a space, `%25` is `%`, a malformed escape such as `%zz` stays as written. The checks of step 4 run on the decoded path, so `%23` (a `#`) is rejected, and `%2E%2E%2F` (`../`) is treated as the path it spells.
- **A URI is opaque after its scheme.** Knott does not decode it, allows `#` and inner whitespace in it, and never compares two URIs. Schemes match without regard to case, so `S3://talks/a.pdf` uses the connector `s3`.
- **A path** is resolved relative to the directory of the entity that contains it. Any regular file inside the vault passes, including a Markdown file, an entity, and a file in a folder whose name starts with `.`. To point at an entity and check its type, use `reference`.
- **The extension** is the text after the last `.` of the file name, lowercased, so `TAKE.MP3` passes `accept: [mp3]`. A name with no `.`, or only a leading one (`.env`), has no extension and fails any `accept`.
- **Knott does not open the file.** An empty or corrupt file passes.

## Issue codes

| Code | Stage | When | `field` / `line` |
|---|---|---|---|
| `schema-duplicate-connector` | schema | two connector files share a `name` | `name` / its line in the second file |
| `file-missing` | file | a required file is absent | the property path / the key's line when present |
| `file-invalid-value` | file | wrong kind of value, unreadable form, a URI in a link, `kid:`, nothing after the scheme, or a path that is empty, absolute or has a `#` | the property path / the value's line |
| `file-unknown-connector` | file | a URI's scheme names no connector | the property path / the value's line |
| `file-outside-vault` | file | a path leaves the vault | the property path / the value's line |
| `file-not-found` | file | no file there with that exact case, or it is a folder | the property path / the value's line |
| `file-extension-mismatch` | file | a vault file's extension is not in `accept` | the property path / the value's line |

`file` is a new stage, listed after `relation`. `schema-invalid-field` and `schema-invalid-yaml` also cover connector files and the `accept` key. No existing code changes meaning. Messages name what was expected, for example ``expects `.mp3` or `.wav`, but `../audio/take.flac` is `.flac` ``. `file-unknown-connector` lists the declared connectors and suggests the closest name; when none is close, it says how to write a vault file whose name has a colon and where to declare the connector.

## CLI and API

### `knott validate`

Resolves the file values of every in-scope entity. A scoped run resolves no file value outside its scope. Output and `--format json` gain nothing but the new issues.

### `knott types --verbose`

- A `file` property shows `file` in the type column, then its extensions when declared: `audio*  file .mp3 | .wav`, `slides  file`, `images  list of file .png | .jpg`.
- A `connectors:` section after `relations:` lists every connector, sorted by name, in the format of the `relations:` section: the name indented by two spaces, then the description and the guidance indented by four. A vault without connectors has no `connectors:` section.

  ```
  connectors:
    gdrive
      The team's shared Google Drive. Written gdrive:<file id from the share link>.
      <!-- Open as https://drive.google.com/file/d/<id>. Upload with the drive skill. -->

    s3
  ```

### `knott view`

The property table shows a `file` property as `types --verbose` does. It draws no edge. The embedded data gains `connectors` and, on each attribute, `accept`.

### Python API

- `Ontology.connectors: list[ConnectorDefinition(name, description, guidance, path)]`, sorted by name; `[]` for a vault without connectors. `ConnectorDefinition` is exported from `knott`.
- `OntologyAttribute.type` may be `file`. One field is added: `accept: list[str]`, `[]` when not declared.

## Edge cases

| Case | Result |
|---|---|
| `audio: ../audio/Take.mp3`, the file on disk is `take.mp3` | `file-not-found`, on macOS as on Linux |
| `audio: ../audio` (a folder) | `file-not-found`: "is a folder, not a file" |
| `slides: s3://talks/ep42.pdf`, `s3` declared | valid |
| `slides: "s3://talks/my slides.pdf#page=3"`, `s3` declared | valid; a URI is opaque |
| `slides: gdrive:1AbC`, `gdrive` declared | valid; a URI needs no `//` |
| `slides: gdrv:1AbC`, only `gdrive` declared | `file-unknown-connector`, suggesting `gdrive` |
| `slides: https://drive.google.com/file/d/1AbC` | `file-unknown-connector`, unless the vault declares a connector named `https` |
| `slides: kid:0190…` | `file-invalid-value`; use a `reference` property |
| `cover: "gdrive:"` | `file-invalid-value`: nothing after the scheme |
| `cover: gdrive:` (unquoted) | not valid YAML for a string: `entity-invalid-frontmatter` |
| `cover: "[cover](gdrive:1AbC)"` | `file-invalid-value`: write a URI on its own |
| `cover: "[cover](../img/a.png)"` | valid; the label is ignored |
| `data: a:b.json` | a URI with scheme `a`: `file-unknown-connector` |
| `data: ./a:b.json` | the path of a file named `a:b.json` |
| `data: C:/Users/me/a.json` | a URI with scheme `c`: `file-unknown-connector` |
| `data: /srv/a.json` | `file-invalid-value`: absolute path |
| `accept: [mp3]` and the value is `gdrive:1AbC` | valid; `accept` applies to paths only |
| `accept: [MP3]` or `accept: [.mp3]` in the concept | `schema-invalid-field` |
| `audio: 42`, or `audio: true` | `file-invalid-value` |
| `audio: "   "` (only whitespace) | `file-invalid-value`: an empty path, as for references |
| `audio: [[take.mp3]]` (unquoted, so YAML reads a nested list) | `file-invalid-value`, suggesting a quoted Markdown link |
| `images: [../img/a.png, "gdrive:1AbC", "s3://talks/b.png"]` | each item resolved on its own; an issue carries `images[1]` and that item's line |
| A symlinked file in the vault that points outside it | `file-outside-vault` |
| `notes: ../scripts/foo.md` (an entity) | valid; no type check |
| `config: ../.knott/concepts/recording.md` | valid; it is a file in the vault |
| An undeclared key whose value looks like a path or a URI | not checked, as for references |
| Two entities name the same file | valid |

## Out of scope

- Transferring files. A connector is a name with guidance; an agent skill or script reads the URIs and moves the files.
- A URL template, or any other machine-readable key on a connector. It would go on the connector file, in a later spec.
- Restricting which connectors one property may use.
- A command that lists file values, reports vault files that no entity points at, or runs `knott refs` on a file path. All three need an index of file values across the vault; a later spec.
- Checking a file's content: a JSON schema, a media type, a size, a checksum.
- A URI in a Markdown link, for `file` or for `kid:` in a reference.
- Entities that mirror a remote page, sync direction and sync state: the [remote sources](../intents/remote-sources.md) intent, which reuses connectors.

## Compatibility

Additive. A concept that declared `type: file` got `schema-invalid-field` before and is now a file property. A vault without `file` properties and without `.knott/connectors/` behaves exactly as in 0.6.1, with the same output. `reference` is unchanged. Ontology API additions only. Version 0.7.0.

Obsidian shows a Markdown link in a property as a link. Whether it opens a non-Markdown vault file from there was not tested for this release; it does not change the value forms.
