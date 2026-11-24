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
    description: Where it is detected - schema, entity, kid, attribute, relation, or file.
  about:
    type: reference
    relation: about
    target: concept
    required: true
    description: The concept whose rule this code enforces.
---
# <!-- The code in backticks, e.g. `kid-missing`. -->

<!-- Cause: one or two sentences saying what knott found wrong. -->

## Example

<!-- A minimal fenced block (frontmatter, or a concept file) that triggers the code. Name the concept in a leading comment line when it matters, e.g. "# concept: senses is a list of objects". -->

## Fix

<!-- What to change, or the command to run, e.g. `knott validate --fix <file>`. -->

## Notes

<!-- Optional: which line or field the issue points at, related codes, edge cases. Delete this section if there is nothing to add. -->
