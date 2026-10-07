---
type: concept
title: Vault
summary: An ordinary directory containing `.knott/`; everything under it is the knowledge base.
spec_section: "§3"
related:
  - "[Entity](entity.md)"
  - "[Schema](schema.md)"
---
# Vault

A vault is any directory with a `.knott/` subdirectory:

```
my-vault/
├── .knott/
│   ├── config.yaml        # knott_version, written once by `knott init`
│   └── schemas/           # one YAML file per entity type
└── … your Markdown, organized however you like
```

## Finding the root

Knott starts at the current directory (or the path you pass) and walks **up** until it finds a directory containing `.knott/`. So `knott validate` works from any subfolder. No vault found → exit code `2`.

## What gets scanned

Every `*.md` file under the root, recursively, except:

- directories whose name starts with `.` (`.git`, `.knott`, `.obsidian`, …)
- symlinked directories (never followed)

`.gitignore` is not consulted. Files are sorted, so output is deterministic.

## Config

`.knott/config.yaml` is optional. If present it must be empty or a YAML mapping; a malformed file is a configuration error (exit `2`). Only `knott init` writes it.
