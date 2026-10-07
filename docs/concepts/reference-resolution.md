---
type: concept
title: Reference resolution
summary: The ordered checks that turn a relation value into a verified link to an entity of the right type.
spec_section: "§11"
related:
  - "[Relation](relation.md)"
  - "[Vault](vault.md)"
---
# Reference resolution

Each reference is resolved **relative to the directory of the file that contains it**. Every check must pass; each failure is reported separately, with its own code:

| # | Check | Failure code |
|---|---|---|
| 1 | value is a string or a list of strings | `relation-invalid-value` |
| 2 | parses as a plain path or Markdown link; no URL scheme, `#fragment`, absolute path; ends in `.md` | `relation-invalid-value` |
| 3 | stays inside the vault root, including through symlinks | `relation-target-outside-vault` |
| 4 | target exists, with **exact case** | `relation-target-not-found` |
| 5 | target is a Knott entity | `relation-target-not-entity` |
| 6 | target's `type` equals the relation's `target` | `relation-target-type-mismatch` |

## Markdown links

`[label](destination)`: the label is ignored. The destination may be wrapped in `<…>` (needed for spaces) or percent-encoded (`%20`). In YAML the whole thing must be quoted.

## Why exact case?

macOS filesystems are case-insensitive by default, Linux's are not. Matching case exactly means a vault validates the same on both.

## Not supported

Wikilinks (`[[note]]`): they resolve by note name rather than path. An unquoted `[[note]]` is even parsed by YAML as a nested list.

All of this lives behind one function, `resolve_reference()` in `src/knott/vault/links.py`, so stable IDs can replace paths later without touching anything else.
