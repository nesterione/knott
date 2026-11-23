---
name: decision
description: A recorded decision.
properties:
  title: {type: string, required: true}
  supersedes: {type: reference, target: decision, relation: supersedes}
  affects:
    type: list
    items: {type: reference, target: concept, relation: about}
  history:
    type: list
    items:
      type: object
      fields:
        replaces: {type: reference, target: decision, relation: supersedes}
---
