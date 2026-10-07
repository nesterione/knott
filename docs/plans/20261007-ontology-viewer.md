# Add `knott view` ontology viewer

## Overview
- Add `knott view [PATH] [-o FILE] [--no-open]`. It draws the vault's ontology (types and the typed relations between them) as one self-contained static HTML page and opens it in the browser.
- Problem: today the only view of the ontology is `knott types --verbose`, which shows no relations, plus a hand-drawn ASCII diagram in `docs/concepts/ontology.md` that goes stale. A full notes graph is too noisy. Users want to see the *structure*.
- What it shows: each type is a pill with its name and entity count. Each edge is a relation, with a solid line for required and a dashed line for optional. Self-relations are drawn as loops. Hovering a type highlights its neighbours. Clicking opens a side panel with the description, attributes, outgoing relations and "Referenced by".
- Three layouts sit behind a toggle: **Layered** (the default), **Force** and **Radial**. Moving between them is animated.
- It plugs into the existing system through a new `Knott.ontology()` API that returns a plain model. The CLI is a thin adapter, as for every other command.

## Context (from discovery)
- `src/knott/api.py`: the `Knott` class (`open`, `schemas`, `schema_issues`, `validate`). `validate` already walks `iter_markdown` + `read_markdown`, which is the same discovery the counts need.
- `src/knott/schema/loader.py`: `load_schemas()` **deletes** relations whose target type is unknown (lines 62-77, issue `schema-unknown-target`). The ghost-node feature needs them kept.
- `src/knott/schema/models.py`: dataclasses `Schema`, `AttributeDef`, `RelationDef`.
- `src/knott/models.py`: public pydantic `_Frozen` models (`SchemaInfo`, `Stats`, …). The new public models go here.
- `src/knott/cli.py`: Typer, `_fail()`, `EXIT_USAGE = 2`, `EXIT_INVALID = 1`. `types` prints the types that loaded and writes the schema errors to stderr.
- `src/knott/skills.py`: precedent for package data. It uses `importlib.resources.files("knott") / "_skills"`. Hatch (`packages = ["src/knott"]`) already ships non-`.py` files, so packaging needs no change.
- `tests/`: `test_api.py`, `test_cli.py` (`CliRunner`, `tmp_path`, `monkeypatch.chdir`), `tests/fixtures/<case>/` vaults (including `unknown-relation-target-type`, `valid-vault`).
- Working prototype (layouts, panel, styling): `docs/plans/20261007-ontology-viewer-prototype.html`. It is the starting point for the template. Delete it when the plan completes.

## Development Approach
- **testing approach**: Regular (code first, then tests)
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
  - write unit tests for new and modified functions
  - cover both success and error scenarios
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- maintain backward compatibility: `validate`/`types` behaviour and issue output stay unchanged

## Testing Strategy
- **unit tests**: `tests/test_schemas.py` (loader change), `tests/test_api.py` (`ontology()`), `tests/test_view.py` (HTML rendering), `tests/test_cli.py` (command).
- `webbrowser.open` is monkeypatched in CLI tests, so no browser launches.
- The layout/interaction JS is **not** unit-tested. It is checked by hand with headless Chrome screenshots of the `docs/` vault in each mode (see Task 6).
- No e2e/UI test framework in this project.
- Check command: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy`

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix

## Solution Overview
- **Model first.** `Knott.ontology()` returns a pydantic `Ontology` (types with attributes, relations and counts, plus the number of schema issues). It is plain data, usable from Python and serialisable as JSON. "Referenced by" and the layouts are *not* stored, because the page computes them.
- **Static page.** One template, `src/knott/_view/ontology.html`, with inline CSS/JS, no CDN and no network. Python replaces the `/*__DATA__*/` placeholder with the model's JSON. `</` is escaped as `<\/` so no schema text can close the `<script>`.
- **No server, no new dependencies.** The page is written to a temp file (or `-o FILE`) and opened with `webbrowser.open`. A live `--watch` mode is out of scope; it could be added later without changing the page.
- **Degrade, don't fail.** Broken schemas still produce a page with whatever loaded, plus a note saying "N schema issues — run `knott validate`". Relations to undefined types are drawn as a ghost node with a dashed outline. Only "no types at all" is a usage error (exit 2).

## Technical Details

**Loader change**: in `load_schemas`, keep the `schema-unknown-target` issue, but move the relation into a new `Schema.unknown_relations: dict[str, RelationDef]` instead of dropping it. Validation keeps ignoring it, because the validator only reads `schema.relations`.

**Public models** (`src/knott/models.py`):
```python
class OntologyAttribute(_Frozen): name: str; type: str; required: bool; description: str | None
class OntologyRelation(_Frozen):  name: str; target: str; required: bool; description: str | None
                                  target_known: bool          # False → ghost node
class OntologyType(_Frozen):      type: str; description: str | None; path: str; count: int
                                  attributes: list[OntologyAttribute]; relations: list[OntologyRelation]
class Ontology(_Frozen):          vault: str; types: list[OntologyType]; schema_issues: int
```
- `vault` is the vault root's directory name. Types are sorted by name, and attributes and relations keep their schema order.
- `count` is the number of Markdown files whose frontmatter `type` equals the type name. Files whose frontmatter is invalid are skipped. Relations are not resolved.

**Renderer** (`src/knott/view.py`):
- `render_ontology(ontology: Ontology) -> str` loads the template through `importlib.resources`, dumps `ontology.model_dump()` to JSON with `ensure_ascii=False`, replaces `</` with `<\/`, and substitutes the placeholder exactly once. A missing placeholder is a programming error (`RuntimeError`).

**CLI**: `knott view [PATH] [-o/--output FILE] [--no-open]`
- `PATH` defaults to `.`, and `Knott.open(PATH)` walks up to the vault root.
- With no `-o`, the page is written to `tempfile.gettempdir()/knott-ontology-<vault>.html`, overwriting the previous one so temp files don't pile up.
- stdout: `Wrote <path>`. When `schema_issues > 0`, stderr also gets `N schema issues — run knott validate`. The exit code is still 0, because the page was made.
- No types → `error: no types to show (add schemas to .knott/schemas/)`, exit 2.

**Page behaviour** (the prototype plus these changes):
- Data comes from the injected JSON instead of the hard-coded `DATA`. The header shows `<vault> · N types · M relations · K entities`.
- The mode is saved in `localStorage` (try/catch) and mirrored in `location.hash` (`#layered|#force|#radial`). On load, the hash wins over storage, and storage wins over the default `layered`.
- Fit to view on load and resize: compute the layout bounds, then scale/translate a root `<g>`.
- Layered: labels sit near the source end of the edge (t ≈ 0.3) instead of the midpoint.
- Ghost nodes: a relation with `target_known: false` gets a synthetic node with a dashed outline and no count. The panel says "undefined type — no schema".
- Radial: the hub is the type with the highest in-degree, ignoring self-loops. A tie goes to the first type by name.
- Schema-issue note: small muted text under the header when `schema_issues > 0`.
- Not doing: search, zoom/pan, entity listing, saved drag positions, PNG export, per-type colours.

## What Goes Where
- **Implementation Steps**: loader change, model + API, renderer + template, CLI command, docs.
- **Post-Completion**: a visual check in a real browser, light and dark.

## Implementation Steps

### Task 1: Keep relations to unknown target types in the loader

**Files:**
- Modify: `src/knott/schema/models.py`
- Modify: `src/knott/schema/loader.py`
- Modify: `tests/test_schemas.py`

- [ ] add `unknown_relations: dict[str, RelationDef]` (default empty) to `Schema`
- [ ] in `load_schemas`, move the relation into `unknown_relations` instead of `del`, and keep the `schema-unknown-target` issue unchanged
- [ ] write test: the `unknown-relation-target-type` fixture gives the relation in `unknown_relations`, not in `relations`, and the issue is still reported
- [ ] confirm the existing validate tests still pass (entity validation ignores unknown relations)
- [ ] run tests - must pass before next task

### Task 2: Add `Ontology` models and `Knott.ontology()`

**Files:**
- Modify: `src/knott/models.py`
- Modify: `src/knott/api.py`
- Modify: `src/knott/__init__.py` (export `Ontology` if other models are exported there)
- Modify: `tests/test_api.py`

- [ ] add `OntologyAttribute`, `OntologyRelation`, `OntologyType` and `Ontology` to `models.py`
- [ ] implement `Knott.ontology()`: load schemas, count entities by type with `iter_markdown` + `read_markdown`, and build sorted types. Unknown relations come last with `target_known=False`
- [ ] write tests on a `tmp_path` vault: a self-relation, a required relation, a relation to a missing type (`target_known=False`), correct counts, a file with invalid frontmatter that is skipped, and a non-entity Markdown file that isn't counted
- [ ] write test: an empty vault returns `types == []`, and a broken schema gives `schema_issues > 0` while the other types are still present
- [ ] run tests - must pass before next task

### Task 3: Add the HTML template and renderer

**Files:**
- Create: `src/knott/_view/ontology.html` (from `docs/plans/20261007-ontology-viewer-prototype.html`)
- Create: `src/knott/view.py`
- Create: `tests/test_view.py`

- [ ] turn the prototype into the template: replace the hard-coded `DATA` with `const DATA = /*__DATA__*/;`, and map the field names to the model (attributes/relations as objects, `count`, `target_known`)
- [ ] apply the page changes from Technical Details: header from data, mode in hash + localStorage, fit to view, layered labels near the source, ghost nodes, schema-issue note, radial tie-break
- [ ] implement `render_ontology()` in `view.py`: the JSON dump, `</` escaping, a single placeholder substitution, and `RuntimeError` if the placeholder is missing
- [ ] write tests: the placeholder is gone, the embedded JSON parses back to the same model, and a description containing `</script><script>alert(1)` does not appear raw in the output
- [ ] write test: the output loads no external URLs (no `src="http`, no `href="http` stylesheet)
- [ ] run tests - must pass before next task

### Task 4: Add the `knott view` command

**Files:**
- Modify: `src/knott/cli.py`
- Modify: `tests/test_cli.py`

- [ ] add `view(path=".", output: Path | None, no_open: bool)`: `Knott.open`, `ontology()`, exit 2 when there are no types, render, write (temp default or `-o`), echo `Wrote <path>`, the stderr note for schema issues, and `webbrowser.open(path.as_uri())` unless `--no-open`
- [ ] write tests: `view --no-open -o out.html` exits 0 and the file contains the vault's type names; without `--no-open`, the monkeypatched `webbrowser.open` is called once with the file URI
- [ ] write tests: an empty vault exits 2 with the error; a vault with one broken schema still writes the page, exits 0 and prints the issue note on stderr; a path that doesn't exist exits 2
- [ ] add `view` to the CLI help test if commands are listed there
- [ ] run tests - must pass before next task

### Task 5: Document the command in the docs vault and README

**Files:**
- Create: `docs/commands/view.md`
- Modify: `docs/concepts/ontology.md`
- Modify: `README.md`

- [ ] create `docs/commands/view.md` (`type: command`, `title: knott view`, `synopsis`, `writes_files: true`, `concepts:` → ontology, schema), with a short description of the layouts, the panel and the flags
- [ ] in `docs/concepts/ontology.md`, keep the ASCII diagram and add "Run `knott view` inside `docs/` to explore it interactively."
- [ ] add a `knott view` row to the README commands table
- [ ] run `uv run knott validate` inside `docs/` - must pass

### Task 6: Verify acceptance criteria
- [ ] run `uv run knott view docs --no-open -o <scratch>/o.html` and take headless Chrome screenshots of `#layered`, `#force` and `#radial` in both light and dark (`--force-dark-mode`). Check that nothing overlaps badly and that labels are readable
- [ ] check a vault with a relation to an undefined type: the ghost node renders and the panel explains it
- [ ] check that the page works offline (no network requests) and that switching modes updates the hash and survives a reload
- [ ] run the full check: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy`

### Task 7: [Final] Update documentation
- [ ] update README.md if needed (Python API: mention `vault.ontology()`)
- [ ] delete `docs/plans/20261007-ontology-viewer-prototype.html`
- [ ] move this plan to `docs/plans/completed/`

## Post-Completion
*Items requiring manual intervention or external systems - no checkboxes, informational only*

**Manual verification**:
- open `knott view` on `docs/` in Safari and Chrome, and try hover, click, panel links, dragging in each mode, and the light/dark switch
- try a larger real vault (10+ types) to see where Layered starts to get crowded. That's the input for any future zoom/pan work
