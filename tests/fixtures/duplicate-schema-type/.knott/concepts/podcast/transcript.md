---
name: transcript
description: >
  Transcript of recorded spoken content.
properties:
  title:
    type: string
    required: true
  created_at:
    type: date
  generated_by:
    type: string
  derived_from:
    type: reference
    target: script
    required: false
    description: >
      The source artifact from which this transcript was produced.
---
