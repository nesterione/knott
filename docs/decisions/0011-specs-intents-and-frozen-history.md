---
type: decision
title: Changes are specified in frozen specs, wanted ones start as intents
status: accepted
decided_on: 2026-11-23
affects:
  - "[Ontology](../concepts/ontology.md)"
---
# 0011: Changes are specified in frozen specs, wanted ones start as intents

**Context.** Work was driven by implementation plans in `docs/plans/`: task checklists with the behaviour scattered through them. Once a plan was done, the exact behaviour of a change (formats, rules, issue codes, edge cases) lived only in SPEC.md, which is rewritten as knott changes, and in plan files nobody reads again. Large decisions such as [0010](0010-concept-files-and-reference-properties.md) started carrying specification detail because there was nowhere else to put it. Wanted-but-unspecified work lived only in GitHub issues, outside the vault agents read. Decisions were changed after the fact by appending "Amended by" notes.

**Decision.**

1. **Three kinds of record, each with one job.**
   - An **intent** (`docs/intents/`) is something we want but haven't specified: the need, an example, open questions. It stays editable. Its `status` is `open` or `dropped`.
   - A **spec** (`docs/specs/NNNN-*.md`) is the exact behaviour of one change: formats, rules, issue codes, CLI and API output, edge cases, out of scope, compatibility. It `realizes` intents and cites the `decisions` it relies on.
   - A **decision** (`docs/decisions/`) stays short: the choice, the rejected alternatives, the reasons. The detail goes in a spec.
2. **SPEC.md is the current state.** Implementing a spec includes updating SPEC.md and the concept, command and issue pages. Specs are the history; SPEC.md is the answer to "how does knott behave now".
3. **Lifecycle.** A spec is `draft` while being written, `accepted` once agreed, and `implemented` once merged. Gaps found during implementation are fixed in the spec itself while it is still accepted. The edit that sets `implemented` also sets `released_in`.
4. **Implemented specs and accepted decisions are never edited again.** A later change writes a new spec (or decision) that `amends` or `supersedes` the old one. The old file is not touched: "superseded by" is found by reverse lookup, the same rule knott applies to relations ([0003](0003-source-side-relations.md)). Fixing a typo or a broken link is the only exception.
5. **Plans are no longer kept.** An execution plan may still be written while implementing a spec, but it is scratch work and is not committed. The completed plans were turned into specs 0001-0005 and `docs/plans/` was removed; git history keeps them.

**Not included.** Intents for every open GitHub issue: they are created when we start specifying one. Tooling that enforces immutability (a check that an implemented spec's file didn't change); review covers it for now.

**Why.**

- **Specs over plans:** a plan answers "what do we do next", a spec answers "what does knott do". Only the second stays useful after the merge, and it is what agents and reviewers check code against.
- **Frozen history:** a record that changes after the fact can't answer "what did we decide then, and why". Pointing forward from the new record keeps each file true to its moment and needs no second edit that can be forgotten.
- **Intents in the vault:** agents read the vault, not GitHub. An intent with validated links to concepts gives them the same context a human gets from the issue.
- **Decisions stay short:** separating why from what keeps both readable. 0010 shows the cost of mixing them.

**Consequences.**

- `docs/` gains two types, `spec` and `intent`. `decision` gains `amends`.
- The "Amended by" notes already appended to 0002, 0003, 0005 and 0008 stay as they are. From now on, a decision that changes another uses `amends`.
- Until reverse lookup exists, finding what superseded a spec means searching for links to it (Obsidian backlinks, or `grep`).
- A pull request that implements a spec updates the spec's status, SPEC.md and the docs in the same change.
