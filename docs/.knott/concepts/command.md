---
name: command
description: A `knott` CLI command.
properties:
  title:
    type: string
    required: true
  synopsis:
    type: string
    required: true
    description: Usage line, e.g. "knott validate [PATH...]".
  writes_files:
    type: boolean
    required: true
    description: Whether the command can create or modify files.
  concepts:
    type: list
    description: Concepts the command operates on.
    items:
      type: reference
      target: concept
---
<!-- Start with the command as an H1, e.g. "# knott validate". -->

<!-- What it does: arguments, defaults, and which files it reads or writes. A table works well when invocations differ. -->

## Output

<!-- Optional: an example of the output in a fenced block, for success and failure. Delete if the command prints nothing worth showing. -->

## Exit codes

<!-- Optional: what each exit code means, e.g. `0` valid, `1` validation errors, `2` usage error. Delete if the command always exits 0. -->
