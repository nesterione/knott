# Add `knott skill install` command

## Overview
- Add a `knott skill install [PATH]` command that copies the bundled `knott` Agent Skill into `PATH/.claude/skills/knott/` and/or `PATH/.agents/skills/knott/`.
- Problem: the skill (`skills/knott/SKILL.md`) is not shipped in the wheel. Users of `uvx knott` have no way to get it except copying it from GitHub by hand.
- Interactive on a TTY with no flags: an arrow-key checkbox (questionary) lets the user choose targets.
- Non-interactive: the `--claude` and `--agents` flags pick targets. With no flags and no TTY, the command exits 2 with a hint.
- Discoverability: `knott --help` says that an agent skill ships with knott and how to install it.

## Context (from discovery)
- `src/knott/cli.py`: a Typer app and a thin adapter over `knott.api`. It has the `_fail` helper, `EXIT_USAGE = 2` and `EXIT_INVALID = 1`, with `✓`/`✗` output style.
- `skills/knott/SKILL.md`: the only skill, currently outside the package.
- `pyproject.toml`: hatchling, `packages = ["src/knott"]`, deps pydantic, pyyaml, typer (0.27, bundles click). mypy strict, ruff.
- `tests/test_cli.py`: `CliRunner`, fixtures use `tmp_path` and `monkeypatch.chdir`.
- Docs: `docs/commands/<cmd>.md` per command, the README "Commands" table, and the README "For agents" section linking the skill.

## Development Approach
- **testing approach**: Regular (code first, then tests)
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
  - write unit tests for new and modified functions
  - cover both success and error scenarios
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- maintain backward compatibility (existing commands unchanged)

## Testing Strategy
- **unit tests**: `tests/test_skills.py` for install logic, `tests/test_cli.py` for the command.
- Interactive mode is tested by monkeypatching the TTY check and the `questionary` prompt functions. No real terminal is needed.
- No e2e/UI tests in this project.
- Check command: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy`

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix

## Solution Overview
- **Bundle**: move the skill into the package at `src/knott/_skills/knott/SKILL.md`, so it ships in the wheel and resolves through `importlib.resources` in both editable and installed mode. (Hatch `force-include` does not apply to editable installs, so the tests would not see the file.)
- **Logic in a module, not the CLI**: `src/knott/skills.py` holds the pure install logic (resolve the bundled tree, compare it, copy it). The CLI only parses flags, prompts and prints. This matches "CLI is a thin adapter".
- **Copy the whole skill directory**, not just `SKILL.md`, so future `references/` files ship without code changes.
- **Command group**: `knott skill` is a Typer sub-app, so the help explains skills and there is room for later subcommands. Only `install` is in scope (YAGNI).

## Technical Details

### CLI surface
```
knott skill install [PATH] [--claude] [--agents] [--force]
```
- `PATH`: project directory (default `.`). It does not need to be a vault and must be an existing directory, else exit 2.
- `--claude` → `PATH/.claude/skills/knott/`; `--agents` → `PATH/.agents/skills/knott/`. Both can be given.
- `--force`: overwrite a target whose contents differ.
- Top-level `knott --help` gets an epilog: "Agent skill: knott ships an Agent Skill for Claude Code, Codex and other agents. Install it into a project with `knott skill install`."
- The `knott skill --help` text explains what the skill is and where the targets go.

### Mode selection
| flags | TTY (stdin and stdout) | behavior |
|---|---|---|
| any of `--claude`/`--agents` | any | install to the flagged targets, no prompts |
| none | yes | `questionary.checkbox` with both targets, `.claude` pre-checked |
| none | no | `error: no target given; pass --claude and/or --agents`, exit 2 |

- Interactive cancel (Ctrl-C → `None`) or an empty selection prints `Nothing installed.` and exits 1.
- The TTY check is `_is_interactive()` in `cli.py`, so tests can monkeypatch it.

### Install semantics (`knott.skills`)
```python
class SkillTarget(StrEnum):
    CLAUDE = "claude"   # .claude/skills
    AGENTS = "agents"   # .agents/skills

class InstallStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"      # existed, differed, overwritten with force
    UNCHANGED = "unchanged"  # identical, nothing written
    CONFLICT = "conflict"    # differs, force not given, nothing written

@dataclass(frozen=True)
class InstallResult:
    target: SkillTarget
    path: Path        # destination skill directory
    status: InstallStatus

def target_dir(root: Path, target: SkillTarget, skill: str = "knott") -> Path
def install_skill(root: Path, target: SkillTarget, *, force: bool = False) -> InstallResult
```
- Comparison: every bundled file must exist at the destination with identical bytes. Extra files at the destination are ignored and never deleted.
- Writes happen only on CREATED/UPDATED. Missing parent directories are created.
- The destination path existing as a file, or not being writable, raises `KnottError` (CLI exit 2).

### Output
```
✓ .claude/skills/knott  installed
✓ .agents/skills/knott  up to date
✗ .agents/skills/knott  differs from bundled skill; rerun with --force to overwrite
```
- Paths are printed relative to `PATH`.
- In interactive mode, a CONFLICT asks `questionary.confirm("Overwrite …?", default=False)` and reinstalls with `force=True` if the answer is yes.
- Exit codes: 0 when everything is installed or up to date, 1 when any conflict remains, 2 for usage or configuration errors.

## What Goes Where
- **Implementation Steps**: code, tests and docs in this repo.
- **Post-Completion**: manual TTY check and the release.

## Implementation Steps

### Task 1: Bundle the skill inside the package

**Files:**
- Move: `skills/knott/SKILL.md` → `src/knott/_skills/knott/SKILL.md`
- Modify: `README.md` (skill link)
- Create: `tests/test_skills.py`

- [x] `git mv skills/knott src/knott/_skills/knott` and remove the empty `skills/`
- [x] update the README "For agents" link to the new path
- [x] build the wheel (`uv build`) and confirm `knott/_skills/knott/SKILL.md` is inside (`unzip -l`)
- [x] write a test: `importlib.resources.files("knott") / "_skills/knott/SKILL.md"` exists and starts with frontmatter `name: knott`
- [x] run tests - must pass before task 2

### Task 2: Install logic in `knott.skills`

**Files:**
- Create: `src/knott/skills.py`
- Modify: `tests/test_skills.py`

- [x] add `SkillTarget`, `InstallStatus`, `InstallResult` and `target_dir`
- [x] implement `install_skill` with tree comparison and copy via `importlib.resources` (`as_file`/`iterdir` traversal)
- [x] raise `KnottError` when the destination is a file or not writable
- [x] write tests: CREATED on an empty dir, UNCHANGED on a second run, CONFLICT on a modified file (file untouched), UPDATED with `force=True`, extra destination files preserved, both targets map to the correct dirs
- [x] write error tests: destination path is a file → `KnottError`
- [x] run tests - must pass before task 3

### Task 3: Add questionary dependency

**Files:**
- Modify: `pyproject.toml`, `uv.lock`

- [x] `uv add questionary` (core dependency)
- [x] confirm `uv run mypy` is clean with questionary types. If not, add a narrow mypy override.
- [x] run tests - must pass before task 4

### Task 4: `knott skill install` command, non-interactive path

**Files:**
- Modify: `src/knott/cli.py`
- Modify: `tests/test_cli.py`

- [x] add a `skill_app = typer.Typer(help=...)` sub-app registered as `skill`, and the `install` command with `PATH`, `--claude`, `--agents` and `--force`
- [x] add `_is_interactive()` and the no-flags/no-TTY error (exit 2)
- [x] add output formatting and exit codes (0/1/2) per Technical Details
- [x] add the epilog to the top-level `app` advertising the skill
- [x] write tests: `--claude`, `--agents`, both; rerun says up to date; conflict exits 1 without `--force` and succeeds with `--force`; nonexistent PATH exits 2; no flags with `_is_interactive` patched False exits 2 with a hint
- [x] write tests: `knott --help` mentions `knott skill install`; `knott skill install --help` lists `--claude`/`--agents`
- [x] run tests - must pass before task 5

### Task 5: Interactive path (questionary)

**Files:**
- Modify: `src/knott/cli.py`
- Modify: `tests/test_cli.py`

- [x] when there are no flags and `_is_interactive()`, show `questionary.checkbox` with `.claude/skills` (checked) and `.agents/skills`
- [x] handle `None` or an empty selection: print `Nothing installed.` and exit 1
- [x] on CONFLICT in interactive mode, ask `questionary.confirm` to overwrite
- [x] write tests (monkeypatch `_is_interactive` → True and a fake `questionary.checkbox(...).ask()`): selection installs the chosen targets; cancel exits 1; confirm yes overwrites, confirm no leaves the file and exits 1
- [x] run tests - must pass before task 6

### Task 6: Verify acceptance criteria
- [x] the skill ships in the wheel and `uvx --from dist/knott-*.whl knott skill install --claude` works in a temp dir
- [x] `knott --help` advertises the skill
- [x] interactive, flag and no-TTY paths all behave as specified
- [x] run the full suite: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy`

### Task 7: [Final] Update documentation
- [x] create `docs/commands/skill.md`, matching the style of the other command pages
- [x] add `knott skill install` to the README Commands table and update "For agents" to say "run `knott skill install`"
- [x] move this plan to `docs/plans/completed/`

## Post-Completion
**Manual verification**:
- run `knott skill install` in a real terminal: arrow keys and space toggle, Enter installs. Ctrl-C aborts cleanly.
- check that Claude Code picks up `.claude/skills/knott/` in a sample project.

**Release**:
- bump the version and publish via the existing GitHub Actions trusted-publishing workflow (see `RELEASING.md`).

## Implementation notes
- ➕ updated the stale `skills/knott/SKILL.md` references in `SPEC.md` and `docs/guides/agent-workflow.md`, and linked the new command page from `docs/README.md`.
- ➕ conflict only when an existing file would be overwritten; a bundled file missing from an otherwise identical install is added without `--force` (status `updated`).
- ➕ `knott skill` gets `short_help` so the command list stays one line; the full text shows in `knott skill --help`.
- ⚠️ `ruff format --check` (no paths) already fails on `main` on Python code blocks in README.md, SPEC.md and docs/guides/python-api.md. That's unrelated to this change; `ruff format --check src tests` is clean.
