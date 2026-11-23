---
name: concept
description: >
  A core idea in Knott's model. Read concepts first to understand what the other documents refer to.
properties:
  title:
    type: string
    required: true
  summary:
    type: string
    required: true
    description: One-sentence definition.
  spec_section:
    type: string
    description: Section of SPEC.md that defines it, e.g. "§9".
  related:
    type: list
    description: Other concepts worth reading next.
    items:
      type: reference
      target: concept
      relation: related
---
# <!-- The concept's name, the same text as the `title` property. -->

<!-- Definition: one or two sentences that name the concept in **bold** and say what it is. The `summary` property holds the one-line version. -->

<!-- Example: a short fenced block (YAML, a diagram, or a command) showing the concept in a real vault. -->

<!-- Rules: a bullet list, each bullet starting with a bold keyword, e.g. "- **Unique** across the whole vault." -->

## <!-- One section per part that needs more than a bullet, e.g. "Discovery", "Value shape", "Not supported". -->

<!-- The details, with links to decisions and other concepts as relative Markdown links. Repeat the heading for each part; delete it if the bullets say everything. -->
