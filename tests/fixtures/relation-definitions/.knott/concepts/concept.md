---
name: concept
properties:
  title: {type: string}
  related:
    type: list
    items: {type: reference, target: [concept, guide], relation: related}
  speakers:
    type: list
    items:
      type: object
      fields:
        role: {type: string}
---
