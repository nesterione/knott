---
name: decision
properties:
  affects:
    type: list
    items:
      type: reference
      target: concept
      relation: about
  supersedes:
    type: reference
    target: decision
    relation: supersedes
---
