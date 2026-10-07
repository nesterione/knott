---
type: decision
title: Strict attribute typing, including YAML 1.1 booleans
status: accepted
decided_on: 2026-10-06
affects:
  - "[Attribute](../concepts/attribute.md)"
  - "[Frontmatter](../concepts/frontmatter.md)"
---
# 0004: Strict attribute typing, including YAML 1.1 booleans

**Context.** PyYAML implements YAML 1.1, so `no`, `yes`, `on`, `off` become booleans and `2026-10-06` becomes a date. Python adds traps of its own: `bool` subclasses `int`, and `datetime` subclasses `date`.

**Decision.** Values are checked by exact type, with no coercion. `count: true` is not an integer, and a datetime is not a date. For `boolean`, Knott also checks the *source spelling*: only `true`/`True`/`TRUE` and `false`/`False`/`FALSE` pass, and `yes`/`no`/`on`/`off` are rejected with "write true or false". The same rule applies to `required:` in schemas.

**Why.** The spec's table says boolean "accepts `true` / `false`, rejects everything else". A code review (Codex) found that the first implementation accepted `flag: yes` because PyYAML had already turned it into `True`; the raw-spelling check closes that gap.

**Consequences.** Error messages suggest quoting when a `string` field receives a number, boolean, or date.
