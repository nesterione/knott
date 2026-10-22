---
type: command
title: knott types
synopsis: knott types [--verbose]
writes_files: false
concepts: "[Schema](../concepts/schema.md)"
---
# knott types

Prints discovered type names, one per line, sorted. `--verbose` adds each type's schema file, description, attributes and relations, so an agent knows what to write before opening the YAML:

```
$ knott types --verbose
lexeme  (.knott/schemas/lexeme.yaml)
  A word with its senses and forms.
  attributes:
    lemma*   string
    tags     list of string
    senses*  list of object
      each item: One sense per meaning.
      id*  string
      ru*  string  Russian gloss
    forms    map of map of string
  relations:
    topic*  → topic
```

A type whose schema says `kid: required` shows `kid: required` under its description. `*` marks a required field. Object fields are indented under their attribute. A relation to a type no schema defines is marked `(undefined type)`. Types are separated by a blank line.

If some schemas have errors, it still prints the types it could load, writes the errors to stderr, and exits `1`.
