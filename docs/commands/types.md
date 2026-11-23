---
type: command
title: knott types
synopsis: knott types [--verbose]
writes_files: false
concepts:
  - "[Schema](../concepts/schema.md)"
---
# knott types

Prints discovered type names, one per line, sorted. `--verbose` adds each type's concept file, description, whether it has a body template, its references, and its properties, so an agent knows what to write before opening the file:

```
$ knott types --verbose
lexeme  (.knott/concepts/lexeme.md)
  A word with its senses and forms.
  kid: required
  template: yes
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

- `kid: required` appears when the concept file says so.
- `template:` is `yes` when the concept file has a body.
- `references:` lists the path of every reference at any depth, or `none`. Paths use `[]` for list items, `.*` for map values and `.field` for object fields.
- `*` marks a required property. Object fields are indented under their property.
- A reference shows its targets after `→`. A target that no concept defines is marked `(unknown)`.

Types are separated by a blank line.

If some concept files have errors, it still prints the types it could load, writes the errors to stderr, and exits `1`. A vault that still has `.knott/schemas/` prints no types and reports [`schema-legacy-layout`](../issues/schema-legacy-layout.md).
