---
type: command
title: knott loops
synopsis: knott loops [NAME] [--format text|json]
writes_files: false
concepts:
  - "[Loop](../concepts/loop.md)"
  - "[Entity](../concepts/entity.md)"
---
# knott loops

Shows where entities stand in the vault's [loops](../concepts/loop.md), and what each one still needs. Run it in the vault. Without `NAME` it prints one line per loop; with `NAME` it lists that loop's entities under their stage.

## Output

```
$ knott loops
episode-production  episode.status  idea 0 · planned 1 · recorded 1 · published 1 · (dropped 1) · no stage 1
```

Each line is the loop, the property it follows, and the entity count of each stage on the path. Side exits are in parentheses. `no stage` counts entities whose property is empty or not an option, and is left out when it is 0.

```
$ knott loops episode-production
planned
  episodes/ep-002/episode.md
    next: recorded — missing recorded_at, transcript in materials
recorded
  episodes/ep-001/episode.md
    next: published — missing published_at, links, summary in materials
published
  episodes/ep-003/episode.md
    ✗ needs `recorded_at`
    ✗ needs a `transcript` in `materials` (`material_for` pointing here)
dropped
  episodes/ep-004/episode.md
no stage
  episodes/ep-005/episode.md
```

- **`next:`** names the following stage and what it still misses, or `ready` when nothing is missing. An entity that fails its own stage is never ready: it shows `after this stage's needs`. The last stage has no `next:` line.
- **`✗ needs`** marks a need of the entity's own stage, or an earlier one, that is not met. `knott validate` reports each as [`loop-stage-unmet`](../issues/loop-stage-unmet.md).
- **Stages with no entities** are left out. Side exits and `no stage` come last.

`--format json` prints `{"loops": [...]}` with, per loop, its definition (stages, needs and guidance), the entities under each stage and side exit, and the unplaced ones. Each entity has `path`, `kid`, `title`, `type` (its own type: the loop's, or a subtype of it), `unmet`, `next` and `missing_next`.

`loops` does not validate entities. Work in progress never changes the exit code.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success, including a vault with no loops (prints nothing) |
| `1` | a concept, relation, connector or loop file has a problem: the loops that loaded are printed, the issues go to stderr |
| `2` | no vault, or `NAME` is not a loaded loop (`error: no loop named <NAME>`) |
