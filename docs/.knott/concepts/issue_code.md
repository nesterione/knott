---
name: issue_code
description: >
  A stable validation issue code reported by `knott validate`, with its cause and how to fix it.
properties:
  code:
    type: string
    required: true
  stage:
    type: string
    required: true
    description: Where it is detected - schema, entity, kid, attribute, or relation.
  about:
    type: reference
    target: concept
    required: true
    description: The concept whose rule this code enforces.
---
<!-- Start with the code in backticks as an H1, e.g. "# `kid-missing`". -->

<!-- Cause: one or two sentences saying what knott found wrong. -->

## Example

<!-- A minimal fenced block (frontmatter, or a schema file) that triggers the code. Name the schema in a leading comment line when it matters. -->

## Fix

<!-- What to change, or the command to run, e.g. `knott validate --fix <file>`. -->

## Notes

<!-- Optional: which line or field the issue points at, related codes, edge cases. Delete if nothing. -->
