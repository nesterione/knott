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
    items:
      type: reference
      target: concept
  supersedes:
    type: reference
    target: decision
---
<!-- Start with "# NNNN: <the decision as a sentence>", the same text as the `title` property; NNNN is the next free number in decisions/. -->

**Context.**

<!-- What problem or gap forced a choice, and what the spec or earlier decisions said. Link GitHub issues (#N) and earlier decisions. -->

**Decision.**

<!-- What was decided. One paragraph, or a list when there are several rules. -->

**Not included.**

<!-- Optional: what this decision deliberately leaves out, and what it waits for. Delete if nothing. -->

**Why.**

<!-- The reasons, and the alternatives that were rejected. -->

**Consequences.**

<!-- What changes for users, agents, and the code; known gaps. When a later decision changes this one, add an "**Amended YYYY-MM-DD** by [NNNN](...)" paragraph at the end instead of rewriting it. -->
