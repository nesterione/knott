---
name: note
properties:
  about:
    type: reference
    target: [episode, meeting]
  sources:
    type: list
    items:
      type: reference
      target: [episode, meeting, podcast]
  mystery:
    type: reference
    target: [podcast, show]
---
