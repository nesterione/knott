---
name: note
properties:
  source:
    type: reference
    target: script
  sources:
    type: list
    items:
      type: reference
      target: script
  required_source:
    type: reference
    target: script
    required: true
  required_sources:
    type: list
    required: true
    items:
      type: reference
      target: script
---
