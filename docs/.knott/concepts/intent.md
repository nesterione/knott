---
name: intent
path: intents
description: >
  Something we want knott to do but have not specified yet: the need, a concrete example, and the open questions. A spec realizes it. Intents stay editable; an intent is "specified" when a spec's `realizes` points at it.
properties:
  title:
    type: string
    required: true
  status:
    type: string
    required: true
    description: open or dropped. Whether a spec realizes it is found by reverse lookup, not stored.
  raised_on:
    type: date
    required: true
  github_issue:
    type: integer
    description: The GitHub issue where it is discussed, if any.
  concepts:
    type: list
    description: Concepts the intent would change.
    items: { type: reference, target: concept }
---
# <!-- The intent as a short phrase, the same text as `title`. -->

## Need

<!-- Who needs what, and what they do today without it. No solution yet. -->

## Example

<!-- One concrete vault or workflow that shows the need: the files, and what should happen. -->

## Open questions

<!-- What a spec has to answer. Remove questions once a spec answers them; keep the answers in the spec, not here. -->
