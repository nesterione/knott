---
name: decision
properties:
  supersedes: {type: reference, target: decision, relation: supersedes}
  amends: {type: reference, target: decision, relation: amends}
  history:
    type: list
    items:
      type: object
      fields:
        replaces: {type: reference, target: decision, relation: supersedes}
---
