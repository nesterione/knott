---
name: episode
properties:
  title:
    type: string
  speakers:
    type: list
    items:
      type: object
      fields:
        person:
          type: reference
          target: person
          required: true
        role:
          type: string
  hosts:
    type: map
    values:
      type: reference
      target: person
  production:
    type: object
    fields:
      team:
        type: reference
        target: team
---
