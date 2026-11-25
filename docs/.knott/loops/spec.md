---
name: spec
description: A change to knott, from a draft spec to a released one.
type: spec
property: status
stages:
  draft:
  accepted:
  implemented: { needs: [released_in] }
---
See [decision 0011](../../decisions/0011-specs-intents-and-frozen-history.md).

## draft

Write the behaviour so that the code and its tests can be checked against it line by line. Link the intents it realizes and the decisions it relies on.

## accepted

Implement it. Fix gaps in the spec itself as you find them. The same change updates SPEC.md, the concept, command and issue pages, and the bundled skill.

## implemented

Set `released_in` in the edit that sets this stage. From here the file is frozen: a later change writes a new spec that `amends` or `supersedes` it.
