---
type: concept
title: Frontmatter
summary: The YAML block between `---` lines at the top of a Markdown file.
spec_section: "§5"
related: "[Entity](entity.md)"
---
# Frontmatter

Parsing rules:

- It starts with `---` on the **first** line (a UTF-8 BOM before it is tolerated).
- It ends at the next line that is exactly `---`.
- LF and CRLF line endings both work.
- YAML is parsed with PyYAML's safe loader (no arbitrary object construction).

If a file starts with `---` but the YAML is invalid, is not a mapping, or never closes, Knott reports `entity-invalid-frontmatter`. It cannot tell whether you meant it to be an entity, so it does not skip it silently.

## YAML 1.1 surprises

PyYAML follows YAML 1.1, where some unquoted values are not strings:

| You write | YAML reads |
|---|---|
| `no`, `yes`, `on`, `off` | boolean |
| `2026-10-06` | date |
| `42`, `0x1F`, `1:30` | integer (`1:30` is 90!) |
| `[label](path.md)` | invalid YAML |

When in doubt, quote: `title: "no"`, `derived_from: "[label](path.md)"`. Knott's error messages suggest quoting when they see these cases.

Line numbers in issues refer to lines in the file (line 1 is the opening `---`).
