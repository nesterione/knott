---
type: intent
title: Loops
status: open
raised_on: 2026-11-25
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Attribute](../concepts/attribute.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Ontology](../concepts/ontology.md)"
---
# Loops

## Need

Many vaults hold work that repeats: every podcast episode goes from an idea to a published episode, every knott spec goes from draft to implemented, every post goes from an idea to a published text. Each pass leaves artifacts behind (a transcript, a summary, a release). Today the vault records only a status value. Nothing says what a status means: which properties must be set by then, and which artifacts must exist. The rules live in a `CLAUDE.md`, so an agent can mark an episode `published` with no summary and `knott validate` passes. There is also no way to see where every episode or spec stands; `knott view` shows types, not entities.

## Example

The podcast vault has `episode` with `status` (`idea`, `planned`, `recorded`, `published`, `dropped`). Transcripts, summaries and topics point at their episode through `material_for`.

With a loop defined for `episode.status`:

- An episode with `status: published` and no `published_at`, or with no summary pointing at it, fails `knott validate`.
- An episode with `status: recorded` and no summary yet is valid. A command lists it under `recorded` with "missing for `published`: `published_at`, `links`, a summary".
- `knott view` shows a board for the loop: one column per stage, one card per episode.
- An agent reads what to do at each stage from the loop file, not from `CLAUDE.md`.

A vault has several loops: the same vault also follows ideas (`open`, `trying`, `adopted`) and decisions. A knowledge base with several workspaces has one loop per kind of activity.

## Open questions

Answered by [spec 0010](../specs/0010-loops.md). Left for a later spec:

- A stage that is derived from links and not stored. An intent is "specified" because a spec's `realizes` points at it; no property holds that.
- A process that crosses types, where the material changes type and folder as it moves (an inbox clipping becomes a source note, then concept notes).
- Requirements on values, not only on presence: a date in the past, a list of at least two.
