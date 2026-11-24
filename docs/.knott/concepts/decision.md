---
name: decision
description: >
  An architecture decision record: a choice made where the spec was silent or ambiguous, and why.
properties:
  title:
    type: string
    required: true
  status:
    type: string
    required: true
    description: accepted, superseded, or proposed.
  decided_on:
    type: date
    required: true
  affects:
    type: list
    required: true
    description: Concepts whose behavior the decision shapes.
    items: { type: reference, relation: about, target: concept }
  supersedes:
    type: reference
    relation: supersedes
    target: decision
  amends:
    type: list
    description: Earlier decisions this one changes in part. The earlier decision is not edited (decision 0011).
    items: { type: reference, relation: amends, target: decision }
---
# <!-- "NNNN: <the decision as a sentence>", the same text as the `title` property; NNNN is the next free number in decisions/. -->

**Context.**

<!-- What problem or gap forced a choice, and what the spec or earlier decisions said. Link GitHub issues (#N) and earlier decisions. Earlier decisions start the text on the label's line. -->

**Decision.**

<!-- What was decided. One paragraph, or a numbered list when there are several rules. -->

**Not included.**

<!-- What this decision deliberately leaves out, and what it waits for. Delete the label if nothing. -->

**Why.**

<!-- The reasons, and the alternatives that were rejected. -->

**Consequences.**

<!-- What changes for users, agents and the code; known gaps. Never edit an accepted decision later: a new decision `amends` or `supersedes` it (decision 0011). -->
