---
type: command
title: knott types
synopsis: knott types [--verbose]
writes_files: false
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Relation](../concepts/relation.md)"
---
# knott types

Prints discovered type names, one per line, sorted. `--verbose` adds each type's concept file, description, whether it has a body template, its references, and its properties, then the vault's relations, so an agent knows what to write before opening the file:

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

If some concept files have errors, it still prints the types it could load, writes the errors to stderr, and exits `1`. A vault that still has `.knott/schemas/` prints no types and reports [`schema-legacy-layout`](../issues/schema-legacy-layout.md).
