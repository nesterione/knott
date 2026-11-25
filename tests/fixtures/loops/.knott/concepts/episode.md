---
name: episode
description: A podcast episode.
properties:
  title: { type: string, required: true }
  status:
    type: enum
    options: [idea, planned, recorded, published, dropped]
  recorded_at: { type: date }
  published_at: { type: date }
  participants:
    type: list
    items: { type: string }
  links:
    type: map
    values: { type: string }
---
