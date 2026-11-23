---
name: bad
properties:
  type:
    type: string
  size:
    type: float
    required: "yes"
  extra:
    type: string
    default: x
  link:
    type: reference
    target: script
    relation: derived
---
