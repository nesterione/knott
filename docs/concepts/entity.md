---
type: concept
title: Entity
summary: A Markdown file whose YAML frontmatter is a mapping with a `type` key.
spec_section: "§5–6"
related:
  - "[Frontmatter](frontmatter.md)"
  - "[Schema](schema.md)"
  - "[Attribute](attribute.md)"
  - "[Relation](relation.md)"
---
# Entity

An entity is one knowledge object, stored as one Markdown file:

```markdown
---
type: transcript
title: Episode 42 transcript
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
---
# Episode 42

The body is arbitrary Markdown. Knott does not read it.
```

- **frontmatter** → structured metadata ([attributes](attribute.md) and [relations](relation.md))
- **body** → free text, opaque to Knott

## Entity or note?

| File | Treated as |
|---|---|
| no frontmatter | ordinary note, ignored |
| frontmatter without `type` | ordinary note, ignored |
| frontmatter with `type` | **entity**, validated |
| starts with `---` but broken YAML | error: `entity-invalid-frontmatter` |

This very folder mixes both: `README.md` is a plain note, everything under `concepts/` is an entity.

## One type

Each entity has exactly one `type`, which must name a [schema](schema.md). There is no inheritance and no multiple typing; connections to other concepts are expressed through relations.

Keys the schema does not declare are allowed and never checked, so personal metadata (`tags`, `aliases`, …) can live alongside typed fields.
