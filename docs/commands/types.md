---
type: command
title: knott types
synopsis: knott types [--verbose]
writes_files: false
concepts: "[Schema](../concepts/schema.md)"
---
# knott types

Prints discovered type names, one per line, sorted. `--verbose` adds each type's schema file and description, so an agent can go straight to the right YAML:

```
$ knott types --verbose
concept  (.knott/schemas/concept.yaml)
  A core idea in Knott's model. …
```

If some schemas have errors, it still prints the types it could load, writes the errors to stderr, and exits `1`.
