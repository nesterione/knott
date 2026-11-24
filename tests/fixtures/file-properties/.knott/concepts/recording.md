---
name: recording
description: A recorded episode with its audio and pictures.
properties:
  title: { type: string, required: true }
  audio: { type: file, required: true, accept: [mp3, wav], description: The mixed take. }
  slides: { type: file }
  images:
    type: list
    items: { type: file, accept: [png, jpg] }
  extras:
    type: map
    values: { type: file }
  credits:
    type: list
    items:
      type: object
      fields:
        photo: { type: file, required: true }
        caption: { type: string }
---
