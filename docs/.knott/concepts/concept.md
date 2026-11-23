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
---
<!-- Start with the title as an H1, the same text as the `title` property. -->

<!-- Definition: one or two sentences that name the concept in **bold** and say what it is. Keep `summary` in the frontmatter as the one-line version. -->

<!-- Example: a short fenced block (YAML, a diagram, or a command) showing the concept in a real vault. -->

<!-- Rules: a bullet list, each bullet starting with a bold keyword, e.g. "- **Unique** across the whole vault." -->

<!-- Add a `##` section for each part that needs more than a bullet: discovery, value shapes, edge cases, why it works this way. Link decisions and other concepts with relative Markdown links. -->
