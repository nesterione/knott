---
type: issue_code
code: loop-stage-unmet
stage: entity
about: "[Loop](../concepts/loop.md)"
---
# `loop-stage-unmet`

An entity is at a stage of a [loop](../concepts/loop.md), but something that stage needs, or an earlier stage needs, is missing: a property is empty, or no entity of the needed type points at it.

## Example

```yaml
# loop: recorded:  { needs: [recorded_at, materials: transcript] }
#       published: { needs: [published_at] }
type: episode
status: published      # no `recorded_at`, and no transcript points here
published_at: 2026-10-02
```

## Fix

Add what is missing: set the property, or create the entity that points here. If the entity isn't that far yet, set the stage property back. `knott loops <name>` lists what every entity needs.

## Notes

One issue per missing need, at the line of the stage property. `(needed since …)` names the earlier stage a need comes from. What the *next* stage needs is never an issue. An entity at a side exit, or with no stage, is not checked. If an old entity can never meet a need, the need is too strict for this vault: remove it from the loop.
