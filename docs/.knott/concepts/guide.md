---
name: guide
description: Task-oriented documentation - how to do something with Knott.
properties:
  title:
    type: string
    required: true
  audience:
    type: string
    required: true
    description: Who it is for - human, agent, or developer.
  concepts:
    type: list
    description: Concepts the guide relies on.
    items:
      type: reference
      target: concept
  commands:
    type: list
    description: Commands the guide uses.
    items:
      type: reference
      target: command
---
<!-- Start with the title as an H1, the same text as the `title` property. -->

<!-- Intro: who the guide is for and what they will be able to do. Then the main steps as a numbered list, each step with the command or file it uses. -->

<!-- Add a `##` section per topic: settings, a worked example, reading results, rules of thumb, a checklist. Link concepts and commands with relative Markdown links. -->
