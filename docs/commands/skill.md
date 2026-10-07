---
type: command
title: knott skill install
synopsis: knott skill install [PATH] [--claude] [--agents] [--force]
writes_files: true
---
# knott skill install

Copies the Agent Skill bundled with Knott into a project, so AI agents working there know how to read schemas, write entities and relations, and run `knott validate`. `PATH` is the project directory, default the current directory. It doesn't need to be a vault.

| Flag | Installs to |
|---|---|
| `--claude` | `PATH/.claude/skills/knott/` (Claude Code) |
| `--agents` | `PATH/.agents/skills/knott/` (Codex and other agents) |

Pass both flags to install to both places. Without either flag, in a terminal, it shows a checkbox to pick the targets (`.claude` is checked by default). Press Esc or Ctrl-C to cancel without installing anything. Without a flag and without a terminal (CI, an agent's shell), it exits `2` and asks for a flag.

A target that already holds the same skill is reported as `up to date` and left alone. A target whose `SKILL.md` differs, for example after local edits, is not overwritten: the command reports it and exits `1`. Rerun with `--force` to overwrite, or answer yes when asked interactively. Files you added next to the skill are never deleted.

```sh
$ knott skill install --claude --agents
✓ .claude/skills/knott  installed
✓ .agents/skills/knott  installed
```

Exit codes: `0` installed or up to date, `1` a target differs (or nothing was selected), `2` usage error, e.g. a `PATH` that doesn't exist.
