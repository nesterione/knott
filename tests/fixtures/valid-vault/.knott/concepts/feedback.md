---
name: feedback
description: Review feedback on a transcript.
properties:
  rating:
    type: integer
  score:
    type: number
  approved:
    type: boolean
  reviewed_at:
    type: datetime
  reviews:
    type: reference
    target: transcript
    required: true
  sources:
    type: reference
    target: script
---
