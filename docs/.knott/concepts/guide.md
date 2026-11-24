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
    items: { type: reference, target: concept }
  commands:
    type: list
    description: Commands the guide uses.
    items: { type: reference, target: command }
---
# <!-- The guide's name, the same text as the `title` property. -->

<!-- Intro: who the guide is for and what they will be able to do. -->

<!-- Steps: a numbered list, each step with the command to run or the file to write. -->

## <!-- One section per topic, e.g. "Required settings", "Reading results", "Rules of thumb". -->

<!-- The details: a worked example, a checklist, or a table. Link concepts and commands with relative Markdown links. Repeat the heading for each topic. -->
