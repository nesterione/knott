---
type: concept
title: Issue
summary: One validation problem, reported as data with a stable code, path, line, field, and message.
spec_section: "§20"
related:
  - "[Ontology](ontology.md)"
---
# Issue

| Field | Meaning |
|---|---|
| `code` | stable kebab-case identifier, see `issues/` |
| `path` | vault-relative path of the file with the problem |
| `line` | 1-based line, when known (omitted rather than guessed) |
| `field` | frontmatter or schema key, when applicable |
| `message` | what was expected vs. what was found |

Text output:

```
✗ transcripts/foo.md:4  derived_from
  relation `derived_from` expects target type `script`
  but `../scripts/foo.md` has type `feedback`

1 validation error
```

Issues are sorted by path, then line. `knott validate --format json` emits the same fields for machines.

Every code has its own page in [`issues/`](../issues/), with cause and fix.
