---
name: note
properties:
  title:
    type: string
  about:
    type: reference
    target: topic
    relation: about
  related:
    type: list
    items:
      type: reference
      target: note
      relation: related
  history:
    type: list
    items:
      type: object
      fields:
        replaces:
          type: reference
          target: note
          relation: supersedes
  roles:
    type: map
    values:
      type: reference
      target: person
  see:
    type: reference
    target: note
---
