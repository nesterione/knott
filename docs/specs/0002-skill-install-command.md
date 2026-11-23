---
type: spec
title: "0002: Ship the agent skill in the package and add `knott skill install`"
status: implemented
created_on: 2026-10-07
released_in: "0.2.0"
---
# 0002: Ship the agent skill in the package and add `knott skill install`

## Summary

The `knott` Agent Skill now ships inside the wheel, and `knott skill install [PATH]` copies it into a project's `.claude/skills/knott/` and/or `.agents/skills/knott/`. Before this, users of `uvx knott` had to copy `SKILL.md` from GitHub by hand. Nothing breaks.

## Behaviour

### Bundled skill

- The skill lives at `src/knott/_skills/knott/` (moved from `skills/knott/`) and is read through `importlib.resources`, so it resolves the same way in editable and installed mode.
- The whole skill folder is installed, not just `SKILL.md`, so files added to it later ship without code changes.

### Targets

| Flag | Destination | For |
|---|---|---|
| `--claude` | `PATH/.claude/skills/knott/` | Claude Code |
| `--agents` | `PATH/.agents/skills/knott/` | Codex and other agents |

Both flags can be given.

### Mode selection

| Flags | stdin and stdout are a TTY | Behaviour |
|---|---|---|
| `--claude` and/or `--agents` | any | install to the flagged targets, no prompts |
| none | yes | a checkbox prompt with both targets; `.claude/skills` is pre-checked |
| none | no | `error: no target given; pass --claude and/or --agents`, exit 2 |

In the prompt, arrows move, space toggles, Enter confirms, and Esc or Ctrl-C cancels. A cancel or an empty selection prints `Nothing installed.` and exits 1.

### Install rules

For each target, the bundled files are compared with the destination:

| Status | When | Writes |
|---|---|---|
| `created` | no bundled file exists at the destination | all files |
| `unchanged` | every bundled file exists with identical bytes | nothing |
| `updated` | some bundled files exist, some differ, and either none of the differing ones exists yet or `--force` is given | the differing files |
| `conflict` | an existing file differs and `--force` is not given | nothing |

- A conflict arises only when an existing file would be overwritten. A bundled file missing from an otherwise identical install is added without `--force`, with status `updated`.
- Extra files at the destination are never changed or deleted.
- Missing parent folders are created.
- In interactive mode, a conflict asks `<path> differs from the bundled skill. Overwrite?` (default no). Yes reinstalls that target with force.

## CLI and API

```
knott skill install [PATH] [--claude] [--agents] [--force]
```

- `PATH` is the project directory, default `.`. It need not be a vault, but it must be an existing directory.
- One line per target, path relative to `PATH`:

```
✓ .claude/skills/knott  installed
✓ .agents/skills/knott  up to date
✗ .agents/skills/knott  differs from bundled skill; rerun with --force to overwrite
```

`updated` prints `✓ <path>  updated`.

| Exit | Meaning |
|---|---|
| `0` | every target installed, updated or up to date |
| `1` | a conflict remains, or the interactive prompt was cancelled or left empty |
| `2` | `PATH` is not a directory, no target and no TTY, the destination exists as a file, or a write failed (`error: cannot write <path>: …`) |

- `knott skill` is a command group. Its help says what the skill is and that it installs to `.claude/skills` (Claude Code) and/or `.agents/skills` (Codex and other agents). Its one-line entry in `knott --help` is "Install the knott Agent Skill for AI agents."
- `knott --help` ends with: "Agent skill: knott ships an Agent Skill for Claude Code, Codex and other agents. Install it into a project with `knott skill install`."

Python (module `knott.skills`, not re-exported from `knott`):

```python
class SkillTarget(StrEnum):  CLAUDE = "claude"; AGENTS = "agents"
class InstallStatus(StrEnum): CREATED; UPDATED; UNCHANGED; CONFLICT
@dataclass(frozen=True)
class InstallResult: target: SkillTarget; path: Path; status: InstallStatus

def target_dir(root: Path, target: SkillTarget, skill: str = "knott") -> Path
def install_skill(root: Path, target: SkillTarget, *, force: bool = False) -> InstallResult
```

`install_skill` raises `KnottError` when the destination exists and is not a directory, or when writing fails.

## Edge cases

- Running the same install twice: the second run prints `up to date`, exit `0`.
- A user edited the installed `SKILL.md`: `conflict`, the file is untouched, exit `1`; with `--force` it is overwritten (`updated`).
- The user added their own file next to the installed skill: kept, and it doesn't count as a difference.
- `.claude/skills/knott` exists as a file: `error: …`, exit `2`.
- No flags in CI (no TTY): exit `2` with the hint, never a hanging prompt.

## Out of scope

Other `knott skill` subcommands, such as uninstalling or listing; only `install` is needed now.

## Compatibility

Additive. Adds the `questionary` dependency. Existing commands are unchanged. The README link to the skill now points at `src/knott/_skills/knott/SKILL.md`. Released as 0.2.0.
