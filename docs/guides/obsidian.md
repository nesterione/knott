---
type: guide
title: Using a vault in Obsidian
audience: human
concepts:
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
commands: "[knott validate](../commands/validate.md)"
---
# Using a vault in Obsidian

A Knott vault is a valid Obsidian vault as-is. Knott skips `.obsidian/` automatically.

## Required settings

Settings → **Files & links**:

| Setting | Value |
|---|---|
| New link format | **Relative path to file** |
| Use [[Wikilinks]] | **off** |

With these, Obsidian writes Markdown links with relative paths, which is exactly what Knott resolves. Since Obsidian 1.11, Markdown links in text and list properties are **clickable** and are **updated when the target moves**.

## Write relations as Markdown links

```yaml
derived_from: "[Episode 42 script](../scripts/episode-42.md)"
```

Plain paths (`../scripts/episode-42.md`) validate too, but aren't clickable in Obsidian.

## The safety net

If Obsidian is configured differently, a rename may rewrite links into wikilinks or vault-absolute paths. `knott validate` rejects those (`relation-invalid-value`), so you notice instead of silently losing the relation.

## Blank properties

Obsidian templates often leave properties empty. Knott treats `null`, `""` (and `[]` for relations) as absent, so blank optional fields don't fail validation.
