---
type: decision
title: Hostile YAML is reported, never crashes or hangs
status: accepted
decided_on: 2026-10-06
affects:
  - "[Frontmatter](../concepts/frontmatter.md)"
  - "[Issue](../concepts/issue.md)"
---
# 0007: Hostile YAML is reported, never crashes or hangs

**Context.** Agents and tools write frontmatter, so Knott must expect malformed input. Review found three cases that escaped the issue model:

- **Alias bombs** (`&a [*a, *a, …]` nested a few levels): PyYAML builds them cheaply by sharing nodes, but Knott's line-number walk revisited shared nodes exponentially and hung.
- **Deep nesting** (thousands of `[`) raised an uncaught `RecursionError`.
- **Invalid characters** (e.g. a NUL byte) raised PyYAML's `ReaderError` before parsing began.
- **Merge-key bombs** (`<<: [*a, *a]` nested): a second Codex pass showed PyYAML's own construction expands these exponentially, and rendering a shared value in an error message could produce megabytes of text.

**Decision.**

- Before constructing values, Knott measures the document's size *after* alias expansion (linear time, memoized per node). Over 100,000 nodes, or a recursive alias, is rejected as invalid YAML.
- The line-number walk runs only after that bound is checked, so it can follow aliases fully (aliased schema fields get the same strict checks). It records only string keys, so a boolean key `true:` can't be confused with `"true":`.
- Values shown in messages are truncated, and lists/mappings are summarized, never printed whole.
- Constructor failures from explicit tags (e.g. `!!bool nope`), recursion, and reader errors all become `entity-invalid-frontmatter` (or a config error, exit `2`, for `.knott/config.yaml`).
- Only `yaml.SafeLoader` is ever used.

**Consequences.** `validate()` keeps its contract: validation problems come back as data, never as exceptions. Each case has a regression test.
