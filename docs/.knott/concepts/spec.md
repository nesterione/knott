---
name: spec
description: >
  A change specification: the exact behaviour one change adds or alters (formats, rules, issue codes, CLI and API output, edge cases). Editable while draft or accepted, frozen once implemented. A later change writes a new spec that amends or supersedes it. SPEC.md holds the current state.
properties:
  title:
    type: string
    required: true
  status:
    type: enum
    required: true
    description: An implemented spec is never edited again; "superseded" is found by reverse lookup, not stored.
    options:
      draft: Being written.
      accepted: Agreed; gaps found while implementing are fixed in the spec itself.
      implemented: Merged and released. Frozen.
  created_on:
    type: date
    required: true
  released_in:
    type: string
    description: The version that shipped it, e.g. "0.5.0". Set in the same edit that marks it implemented.
  github_issues:
    type: list
    description: GitHub issue numbers this spec closes, for specs written before intents existed.
    items:
      type: integer
  realizes:
    type: list
    description: The intents this spec turns into behaviour.
    items: { type: reference, target: intent }
  decisions:
    type: list
    description: The decisions whose reasoning this spec relies on.
    items: { type: reference, target: decision }
  concepts:
    type: list
    description: Concepts whose behaviour this spec defines or changes.
    items: { type: reference, target: concept }
  amends:
    type: list
    description: Earlier specs this one changes in part. The earlier spec is not edited.
    items: { type: reference, relation: amends, target: spec }
  supersedes:
    type: list
    description: Earlier specs this one replaces entirely. The earlier spec is not edited.
    items: { type: reference, relation: supersedes, target: spec }
---
# <!-- "NNNN: <what the change does>", the same text as `title`; NNNN is the next free number in specs/. -->

## Summary

<!-- Two to four sentences: what a user can do after this change that they couldn't before, and what breaks, if anything. -->

## Behaviour

<!-- The rules, exactly. File formats with a short example, allowed keys, value rules, resolution order. One `###` subsection per area. Write it so the implementation and its tests can be checked against it line by line. -->

## Issue codes

<!-- A table of codes added, changed or removed: code, stage, when it is reported, `field` and `line`. Delete the section if none. -->

## CLI and API

<!-- New or changed commands, flags, output (show it), exit codes, and public Python API. Delete the section if none. -->

## Edge cases

<!-- The cases that are easy to get wrong, each with the expected result. -->

## Out of scope

<!-- What this spec deliberately leaves out, and where it would go. -->

## Compatibility

<!-- Breaking or additive; what existing vaults and API users must do; the version bump. -->
