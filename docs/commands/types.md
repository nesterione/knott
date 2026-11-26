---
type: command
title: knott types
synopsis: knott types [--verbose] [--tree]
writes_files: false
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Relation](../concepts/relation.md)"
---
# knott types

Prints discovered type names, one per line, sorted. `--verbose` adds each type's concept file, description, whether it has a body template, its references, and its properties, then the vault's relations, connectors and loops, so an agent knows what to write before opening the file:

```
$ knott types --verbose
lexeme  (.knott/concepts/lexeme.md)
  A word with its senses and forms.
  kid: required
  template: yes
  path: lexemes/**
  filename: {lemma}.md
    lemma  [a-ząčęėįšųūž]+  The dictionary form, lowercase.
  references: senses[].see_also, topic
  properties:
    lemma*   string
    tags     list of string
    senses*  list of object
      each item: One sense per meaning.
      id*       string
      ru*       string              Russian gloss
      see_also  reference → lexeme
    forms    map of map of string
    topic*   reference → topic | lesson (unknown)
```

- `extends: <parent>`, `abstract: yes` and `subtypes:` (the direct children) appear for a type in a [hierarchy](../concepts/schema.md#inheritance). An inherited template, `path`, `filename` or `kid` ends with `(from <type>)`, and inherited properties come first, in a `properties (from <type>):` block per ancestor.
- `kid: required` appears when the concept file says so.
- `template:` is `yes` when the concept file has a body.
- `path:` appears when the concept file says [where its entities are stored](../concepts/schema.md#where-entities-live); several patterns are joined with ` | `.
- `filename:` appears when the concept file sets [a pattern for file names](../concepts/schema.md#file-names), followed by one line per part: its name, the expression it must match, and how to fill it.
- `references:` lists the path of every reference at any depth, or `none`. Paths use `[]` for list items, `.*` for map values and `.field` for object fields.
- `*` marks a required property. Object fields are indented under their property.
- A reference shows its targets after `→`; an [open reference](../concepts/relation.md#open-references) shows `→ any`. A target that no concept defines is marked `(unknown)`.
- An [enum](../concepts/attribute.md#enums) lists its options on the lines under it: `one of: m | f`, or one line per option when any has a description (`A1: Understands …`).
- A [file](../concepts/file.md) shows the extensions it accepts: `audio*  file .mp3 | .wav`, `images  list of file .png | .jpg`.
- A reference that names a [relation](../concepts/relation.md) shows it in parentheses after the type: `affects*  list of reference → concept  (about)`. A name no relation file defines is not shown.

Types are separated by a blank line.

## Relations

A vault with relation files gets a `relations:` section after the types, sorted by name. Each relation is one line with its name, then `inverse: <x>`, `symmetric` and `acyclic` as they apply, followed by its description and its guidance (the file's body), indented. From this folder, shortened (`amends` and most guidance left out):

```
relations:
  about  inverse: discussed_in
    The source discusses the target, shapes its behaviour or enforces its rules. Read from the target, the source is where the target is discussed.
    Use `about` when the target is the subject the source is written about: …

  related  symmetric
    The two entities are worth reading together. The link goes both ways.
    Use `related` between peers, such as two concepts that explain each other. …

  supersedes  inverse: superseded_by  acyclic
    This entity replaces the target entirely. The target is kept unchanged as history.
    Use `supersedes` when the old record is no longer the current answer: …
```

A vault without relation files has no `relations:` section.

## Connectors

A vault with [connector files](../concepts/file.md#uris-and-connectors) gets a `connectors:` section last, sorted by name, in the same format: the name, then its description and guidance indented.

```
connectors:
  gdrive
    The team's shared Google Drive. Written gdrive:<file id from the share link>.
    <!-- Open as https://drive.google.com/file/d/<id>. Upload with the drive skill. -->

  s3
```

If some concept files have errors, it still prints the types it could load, writes the errors to stderr, and exits `1`. A vault that still has `.knott/schemas/` prints no types and reports [`schema-legacy-layout`](../issues/schema-legacy-layout.md).

A vault with [loops](../concepts/loop.md) gets a `loops:` section after that, sorted by name: the loop and the property it follows, its description, the path, the side exits, what each stage needs, and the guidance.

```
loops:
  episode-production  episode.status
    From an episode idea to a published episode.
    stages: idea → planned → recorded → published
    exits: dropped
    planned needs: participants
    recorded needs: recorded_at, transcript in materials
    ## recorded
    Export the transcript into the episode folder.
```

## Tree

`--tree` (`-t`) prints the types as a tree: each type's subtypes are indented under it, with its entity count and the folder its entities live in. Use it to see a vault's taxonomy on one screen.

```
$ knott types --tree
concept            12  concepts
note                3
record (abstract)
├─ decision        12  decisions
└─ spec            14  specs
```

- **Order**: types with no parent first, sorted by name, each followed by its direct subtypes, sorted. A vault without [inheritance](../concepts/schema.md#inheritance) prints a flat list.
- **Count**: entities whose `type` is exactly that type. Subtypes are not added in. An abstract type has no count.
- **Folder**: the type's `path` patterns, its own or inherited, joined with ` | `. Left out when it has none.
- `--tree` reads every Markdown file in the vault to count entities; plain `knott types` reads concept files only.

`--tree --verbose` adds, under each type, its description on one line and `adds:` with the properties it declares itself (`*` marks a required one). Inherited properties are listed at the type that declares them.

```
$ knott types --tree --verbose
concept            12  concepts
   A core idea in Knott's model. Read concepts first to understand what the other documents refer to.
   adds: title*, summary*, spec_section, related
note                3
record (abstract)
│  Anything with a title and a date.
│  adds: title*, created_on*
├─ decision        12  decisions
│     Why a choice was made.
│     adds: status*, supersedes
└─ spec            14  specs
      The exact behaviour one change adds or alters.
      adds: status*, realizes, decisions, concepts
```

The tree leaves out the relations, connectors and loops sections, and the shapes, targets and options of properties. Those are in `knott types --verbose`.
