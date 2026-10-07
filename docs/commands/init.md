---
type: command
title: knott init
synopsis: knott init [PATH]
writes_files: true
concepts: "[Vault](../concepts/vault.md)"
---
# knott init

Creates `.knott/schemas/` and `.knott/config.yaml` (recording `knott_version`) in `PATH`, default the current directory. It creates no content folders. Organize your Markdown however you like.

If `.knott/` already exists, it changes nothing, says the vault is already initialized, and exits `0`. A `PATH` that doesn't exist exits `2`.
