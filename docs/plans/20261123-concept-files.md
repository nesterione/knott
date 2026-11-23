# Concept files and reference properties (decision 0010)

## Overview
- Implement [decision 0010](../decisions/0010-concept-files-and-reference-properties.md) for knott v0.5.
- Each type is defined by a Markdown file in `.knott/concepts/**/*.md`. Its frontmatter is the schema, identified by `name:`. Its optional body is a template for entity bodies, with `<!-- -->` guidance. Knott stores the body but never checks entities against it.
- `attributes` and `relations` merge into one `properties` map. `reference` is a shape (`type: reference`, `target: <type>` or `target: [a, b]`) usable at any depth. Cardinality is strict: `reference` holds one; several is `list` of `reference`.
- The `relation:` key on a reference and the `.knott/relations/` folder are reserved (errors).
- Old `.knott/schemas/` vaults get `schema-legacy-layout` and a `knott migrate` command that converts them.
- Problems solved: references inside structured values (0008's gap), union targets (#1), one ordered map, a home for body templates.

## Context (from discovery)
- `src/knott/schema/models.py`: `Shape = ScalarType | ListShape | ObjectShape | MapShape`. `AttributeDef(name, shape, required, description)`. `RelationDef` and `Schema.relations` / `unknown_relations` go away.
- `src/knott/schema/loader.py`: `discover_schema_files` globs `.knott/schemas/**/*.yaml`. `load_schemas` parses, catches `schema-duplicate-type`, then checks relation targets (`schema-unknown-target`) and moves unknown ones to `unknown_relations`. `_SchemaParser` has `_parse_attributes`, `_parse_definition`, `_parse_shape`, `_parse_object`, `_parse_relations`, plus `schema-field-conflict` (line ~155).
- `src/knott/schema/validator.py`: `validate_entity` checks attributes via `_check_value` (recursive, reports full paths through `format_field_path`), and relations separately. `is_absent_relation` encodes 0005's relation column.
- `src/knott/vault/entity.py`: `parse_markdown(text, rel_path)` → `MarkdownFile` with frontmatter, nested key lines and body. Reuse it to read concept files.
- `src/knott/vault/discovery.py`: `iter_markdown` already skips dot-directories, so concept files are never discovered as entities.
- `src/knott/vault/links.py`: `resolve_reference()` stays as it is.
- `src/knott/api.py`: `Knott.init` creates `.knott/schemas/`. `ontology()` builds `OntologyType(attributes, relations)` via `_ontology_attribute` and a local `relation()` helper. `_validate` counts resolved relations for stats.
- `src/knott/models.py`: public `OntologyAttribute` (recursive since 0008), `OntologyRelation`, `OntologyType`, `Ontology`, `SchemaInfo`.
- `src/knott/cli.py`: `format_type` / `_attribute_lines` for `types --verbose`. `view` renders `src/knott/_view/ontology.html`, which draws edges from `relations`.
- `src/knott/_skills/knott/SKILL.md`: describes `.knott/schemas/**/*.yaml`, `attributes` and `relations`.
- Tests: `tests/test_schemas.py`, `test_attributes.py`, `test_relations.py`, `test_entities.py`, `test_kid.py`, `test_fix.py`, `test_api.py`, `test_cli.py`, `test_view.py`, `test_skills.py`; fixtures in `tests/fixtures/<case>/.knott/schemas/`.
- Docs vault: `docs/.knott/schemas/{concept,command,decision,guide,issue_code}.yaml`.
- Commands: `uv run pytest`, `uv run ruff check src tests`, `uv run mypy`.

## Development Approach
- **testing approach**: Regular (code first, then tests in the same task)
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
  - write unit tests for new functions/methods
  - write unit tests for modified functions/methods
  - add new test cases for new code paths
  - update existing test cases if behavior changes
  - tests cover both success and error scenarios
- **CRITICAL: all tests must pass before starting next task** - no exceptions
- **CRITICAL: update this plan file when scope changes during implementation**
- run tests after each change (`uv run pytest && uv run ruff check src tests && uv run mypy`)
- backward compatibility: **intentionally broken** for the schema format and the Python ontology API (decision 0010, pre-1.0). Entities stay compatible. `knott migrate` is the bridge.

## Testing Strategy
- **unit/behavior tests**: fixture vaults under `tests/fixtures/<case>/`, as today. Every new rule gets a fixture or an inline `tmp_path` vault.
- **no e2e UI suite**: `knott view` is covered by `tests/test_view.py`, which checks the generated HTML/JSON payload.

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## Solution Overview
- **Converter first.** A pure function turns a legacy YAML schema plus cardinality hints into concept-file text. It is used twice: to convert test fixtures and the docs vault in one pass, and by `knott migrate`. The old parser is never kept alongside the new one.
- **One shape system.** `ReferenceShape(targets: tuple[str, ...])` joins the `Shape` union. Loader, validator, ontology and view all walk shapes; one helper `iter_references(schema)` yields `(key_path, ReferenceShape)` for anything that needs edges (target checks, ontology, view, stats).
- **Concept files reuse entity parsing.** `parse_markdown` already gives frontmatter, key lines and body, so concept files get exact line numbers for free.
- **Legacy layout stops the run early.** If `.knott/schemas/` exists, knott reports one `schema-legacy-layout` issue and skips loading and entity checks. Otherwise every entity would also report `entity-unknown-type`, burying the one issue that matters.

## Technical Details

**Concept file**
```yaml
---
name: transcript                # required, ^[a-z][a-z0-9_-]*$
description: ...                # optional string
kid: required                   # optional, as today
properties:                     # optional map: name → definition
  title:        { type: string, required: true }
  derived_from: { type: reference, target: script }
  sources:
    type: list
    items: { type: reference, target: [script, episode] }
---
<optional body template, stored verbatim>
```
- Allowed top-level keys: `name`, `description`, `kid`, `properties`. A `type:` key → `schema-invalid-field` with "concept files use `name:`; `type:` belongs to entities". `attributes:` / `relations:` → `schema-invalid-field` with "merged into `properties` (decision 0010); run `knott migrate`".
- A file with no frontmatter → `schema-invalid-yaml` ("a concept file needs YAML frontmatter").
- Top-level property names `type` and `kid` stay reserved.
- Reference definition keys: `type`, `target`, `required`, `description`. `target` is a non-empty string or a non-empty list of unique strings. `relation` → `schema-invalid-field` ("reserved for relation definitions, not supported yet"). `required` on `items` / `values` is still rejected (0008).
- `schema-unknown-target`: reported per unknown name, `field` = full schema path (`properties.sources.items.target`). Unknown names are dropped from `targets`. If none are left, the reference keeps its shape (value kind and path resolution are still checked), but the target-type check is skipped. This matches today's `unknown_relations`, which stay displayed but are not enforced.
- `.knott/relations/` exists → `schema-invalid-field` at path `.knott/relations` ("reserved for relation definitions (decision 0010), not supported yet").
- Duplicate `name` → `schema-duplicate-type` (code kept), message names both files.
- `schema-field-conflict` is removed from code and docs.

**Validation of reference values** (amended 0005)
| Value | `reference` | `list` of `reference` |
|---|---|---|
| `null` / `""` | absent | absent |
| `[]` | `relation-invalid-value` | absent |
| `{}` | `relation-invalid-value` | `relation-invalid-value` |
| string | resolve | `relation-invalid-value` ("expects a list of references") |
| list | `relation-invalid-value` ("expects one reference; declare `type: list` for several") | each item resolved; a null / empty item is `relation-invalid-value` |
- A required reference that is absent → `relation-missing`. A required list of references that is absent → `relation-missing` (not `attribute-missing`): a list or map whose items are references counts as a reference property for code choice.
- Target type check: the entity's type must be in `targets`. The mismatch message lists all of them (`expects \`episode\` or \`meeting\``).
- `field` is the full path (`speakers[1].person`), and `line` is the nested key or item line.
- Stats `relations` counts every resolved reference at any depth.

**Public API (`knott.models`)**
- `OntologyAttribute` gains `targets: list[str]` (empty unless `type == "reference"`) and `unknown_targets: list[str]`. `notation` renders `reference → script`, `list of reference → script | episode`.
- `OntologyType`: `attributes` + `relations` → `properties: list[OntologyAttribute]`. Add `template: str | None` (the body, `None` when empty) and a convenience `references() -> list[tuple[str, OntologyAttribute]]` (dotted path, reference node) for edges.
- `OntologyRelation` is removed. `SchemaInfo.path` now points at the concept file.

**`knott migrate [PATH]`**
- Finds the vault, reads every `.knott/schemas/**/*.yaml` with the safe loader (0007 limits apply), and maps each to `.knott/concepts/<same relative path>.md`.
- Conversion: `type` → `name`. `description` and `kid` are kept. `attributes` then `relations` go into `properties`, in file order. A relation becomes `{type: reference, target, description}`, or `{type: list, required, description, items: {type: reference, target}}` when any entity of that type stores a list in that field; `required` moves to the list.
- Output YAML: block style, `sort_keys=False`, `width` wide enough to keep descriptions on one line, folded `>` for multi-line descriptions. The body is empty.
- Refuses (exit 2, nothing written) when: there is no `.knott/schemas/`; any legacy file fails to parse or has unknown keys; a target `.md` already exists.
- On success: writes all files, deletes `.knott/schemas/`, then runs `validate()` and prints its result. Exit code = the validation exit code.
- API: `Knott.migrate() -> MigrateResult(written: list[str], removed: str, list_fields: list[str])`. It runs before the vault is loaded, so it works on a vault that reports `schema-legacy-layout`.

**`knott init`** creates `.knott/concepts/` instead of `.knott/schemas/`.

## What Goes Where
- **Implementation Steps**: code, tests, fixtures, docs vault, SPEC, skill, README.
- **Post-Completion**: release v0.5 per `RELEASING.md`, migrate external vaults.

## Implementation Steps

### Task 1: Legacy-schema converter (pure function)

**Files:**
- Create: `src/knott/schema/migrate.py`
- Create: `tests/test_migrate.py`

- [ ] add `convert_legacy(data: dict, list_fields: set[str]) -> str` returning concept-file text (frontmatter only), following the conversion rules in Technical Details
- [ ] add `legacy_list_fields(schema_type, relation_names, entities)` that returns the relation names any entity of that type stores as a YAML list
- [ ] keep key order: `name`, `description`, `kid`, `properties` (attributes, then relations, each in file order)
- [ ] write tests: scalar/nested attributes pass through unchanged; a relation becomes `reference`; a list-used relation becomes `list` of `reference` with `required` on the list; descriptions (incl. multi-line) survive; output re-parses to the expected dict
- [ ] write tests for error cases: non-mapping input, missing `type`, unknown top-level keys raise `MigrateError` with the offending key
- [ ] run tests - must pass before next task

### Task 2: Reference shape, concept loader and fixture conversion

**Files:**
- Modify: `src/knott/schema/models.py`
- Modify: `src/knott/schema/loader.py`
- Modify: `src/knott/vault/discovery.py` (constants: `CONCEPTS_DIR`, `RELATIONS_DIR`, `LEGACY_SCHEMAS_DIR`)
- Modify: `tests/fixtures/*/.knott/` (all fixtures: `schemas/*.yaml` → `concepts/*.md`)
- Modify: `tests/test_schemas.py`

- [ ] add `ReferenceShape(targets: tuple[str, ...], unknown: tuple[str, ...] = ())` to the `Shape` union. Update `shape_kind` / `notation`, and add `iter_references(schema)`
- [ ] replace `Schema.attributes` / `relations` / `unknown_relations` with `properties: dict[str, AttributeDef]` plus `template: str | None`. Delete `RelationDef`
- [ ] rewrite discovery and parsing: `.knott/concepts/**/*.md` via `parse_markdown`. Top-level keys `name`/`description`/`kid`/`properties`, with the targeted messages for `type`, `attributes`, `relations`, and no frontmatter
- [ ] parse `type: reference` (`target` string or list, `relation` reserved) at any depth. Resolve targets after all files load (`schema-unknown-target` per unknown name, full field path). Report `.knott/relations/` as reserved. Remove `schema-field-conflict`
- [ ] detect `.knott/schemas/`: `load_schemas` returns a single `schema-legacy-layout` issue (path `.knott/schemas`, message names `knott migrate`) and an empty registry
- [ ] convert every fixture with Task 1's converter (one-off script in the session scratchpad, not committed; cardinality from each fixture's entities). Hand-fix fixtures whose entities rely on one-or-list leniency, and record each one in this plan with ➕
- [ ] update `tests/test_schemas.py` for the new paths and keys. Drop the `schema-field-conflict` cases. Add cases: `type:` in a concept file, `attributes:`/`relations:` keys, no frontmatter, `relation:` key, empty/duplicate `target` list, unknown target inside `items` and object `fields`, `.knott/relations/` present, legacy layout, duplicate `name`, template stored verbatim / `None` when blank
- [ ] run tests - schema tests must pass. Entity/relation tests may fail until Task 3 (mark them with a TODO naming Task 3)

### Task 3: Validate references at any depth

**Files:**
- Modify: `src/knott/schema/validator.py`
- Modify: `src/knott/api.py` (`_validate` stats, skip entity checks on legacy layout)
- Modify: `tests/test_relations.py`, `tests/test_attributes.py`, `tests/test_entities.py`
- Create: `tests/fixtures/nested-references/`, `tests/fixtures/union-target/`, `tests/fixtures/reference-cardinality/`

- [ ] handle `ReferenceShape` inside `_check_value`: string → `resolve_reference` + target-type check against `targets`; the empty/kind rules from the table; codes `relation-*` with full `field` path and nested line
- [ ] use `relation-missing` for an absent required reference, or for a list or map of references. Remove the separate top-level relation loop and `is_absent_relation`
- [ ] count resolved references at every depth in stats. With `schema-legacy-layout`, return early with only that issue
- [ ] write tests: nested references in object fields, list items and map values (valid + not found + wrong type, exact `field` and `line`); union targets (each allowed type passes; a mismatch lists all); `kid:` references nested
- [ ] write tests for cardinality and emptiness: list given for `reference`, string given for a list, `[]`/`{}`/null for both, null item in a list, required list empty → `relation-missing`; legacy layout reports one issue and no `entity-unknown-type`
- [ ] remove the Task 2 TODOs; run tests - must pass before next task

### Task 4: Public ontology model and API

**Files:**
- Modify: `src/knott/models.py`
- Modify: `src/knott/api.py` (`ontology()`, `_ontology_attribute`, `schemas()`)
- Modify: `src/knott/__init__.py`
- Modify: `tests/test_api.py`

- [ ] add `targets` / `unknown_targets` to `OntologyAttribute`, extend `notation`
- [ ] replace `OntologyType.attributes`/`relations` with `properties`. Add `template` and `references()`. Delete `OntologyRelation` and its export
- [ ] build properties recursively from `AttributeDef`, references included
- [ ] write tests: ontology for a vault with nested + union references (`properties` order, `targets`, `unknown_targets`, `references()` paths like `speakers[].person`, `template` text)
- [ ] write tests for edge cases: concept with no properties, blank body → `template is None`, all targets unknown
- [ ] run tests - must pass before next task

### Task 5: `knott types --verbose` and `knott view`

**Files:**
- Modify: `src/knott/cli.py`
- Modify: `src/knott/_view/ontology.html`
- Modify: `src/knott/view.py` (if the payload builder lives there)
- Modify: `tests/test_cli.py`, `tests/test_view.py`

- [ ] `types --verbose`: one properties list in schema order, references shown as `derived_from → script`, `sources: list of reference → script | episode`, nested under objects as today. Add a `references` summary line per type, and show `template: yes/no`
- [ ] view: draw edges from `references()` (one edge per target, labelled with the property path). The side panel shows one properties table and the template in a collapsible block
- [ ] write tests: CLI output snapshot for nested/union references and unknown targets
- [ ] write tests: view payload has edges for nested and union references and none for unknown targets; template included
- [ ] run tests - must pass before next task

### Task 6: `knott migrate` and `knott init`

**Files:**
- Modify: `src/knott/schema/migrate.py` (vault-level `migrate_vault`)
- Modify: `src/knott/api.py` (`Knott.migrate`, `Knott.init`)
- Modify: `src/knott/models.py` (`MigrateResult`)
- Modify: `src/knott/errors.py` (`MigrateError` as a `KnottError`)
- Modify: `src/knott/cli.py` (`migrate` command)
- Modify: `tests/test_migrate.py`, `tests/test_cli.py`, `tests/test_api.py`
- Create: `tests/fixtures/legacy-layout/`

- [ ] implement `migrate_vault(root)`: read legacy files (safe loader), scan entities for list-valued relations, convert, refuse on any parse error / unknown key / existing target file before writing anything, then write all files and remove `.knott/schemas/`
- [ ] `Knott.migrate()` works without loading schemas. The CLI prints written files and list-converted fields, then the validation result. Exit codes per Technical Details
- [ ] `Knott.init` creates `.knott/concepts/`
- [ ] write tests: migrating `legacy-layout` (copied to `tmp_path`) produces the expected files and a valid vault; a relation used as a list becomes `list` of `reference`; nested-schema subfolders keep their relative path
- [ ] write tests for refusals: no legacy dir, broken YAML, unknown key, existing concept file. Nothing is written or deleted in each case; `init` creates `concepts/`
- [ ] run tests - must pass before next task

### Task 7: Agent skill

**Files:**
- Modify: `src/knott/_skills/knott/SKILL.md`
- Modify: `tests/test_skills.py` (if it asserts content)

- [ ] describe concept files (`.knott/concepts/**/*.md`, `name:`, `properties`, `type: reference`), and tell agents to start new entity bodies from the concept's template, deleting the `<!-- -->` guidance once a section is filled
- [ ] document cardinality (`reference` vs `list` of `reference`), nested references and union targets in the reference-writing section
- [ ] add: on `schema-legacy-layout`, run `knott migrate` and review the diff
- [ ] update skill tests if they check paths or headings
- [ ] run tests - must pass before next task

### Task 8: Convert the docs vault and write templates

**Files:**
- Delete: `docs/.knott/schemas/*.yaml`
- Create: `docs/.knott/concepts/{concept,command,decision,guide,issue_code}.md`

- [ ] run `uv run knott migrate docs`, then check the diff
- [ ] write body templates from the existing documents' structure: `concept` (definition, example, rules), `decision` (Context / Decision / Not included / Why / Consequences), `issue_code` (cause, example, fix), `command`, `guide`
- [ ] `uv run knott validate docs` passes; `uv run knott types --verbose` inside `docs/` shows the templates
- [ ] run full tests - must pass before next task

### Task 9: SPEC, concept docs, issue docs, README

**Files:**
- Modify: `SPEC.md` (§4 discovery, §7 format, §8–11 attributes/relations/references, §13 validation, §14 CLI incl. `migrate`, §20 issue codes, §21 API)
- Modify: `docs/concepts/{schema,attribute,relation,ontology,reference-resolution,kid}.md`
- Modify: `docs/guides/{writing-schemas,getting-started,agent-workflow,python-api}.md`, `docs/commands/{init,types,view}.md`
- Create: `docs/commands/migrate.md`, `docs/issues/schema-legacy-layout.md`
- Modify: `README.md`

- [ ] rewrite schema docs around concept files, `properties`, `reference`, templates; the relation concept describes reference properties plus the reserved relation definitions (0010 §7)
- [ ] issue codes: add `schema-legacy-layout`, remove `schema-field-conflict`, update the `relation-*` texts for nested paths and cardinality
- [ ] add the `migrate` command page and README section ("Upgrading from 0.4")
- [ ] `uv run knott validate docs` passes
- [ ] run full tests - must pass before next task

### Task 10: Verify acceptance criteria
- [ ] every point of decision 0010 §1–8 is implemented or explicitly reserved
- [ ] edge cases: unknown targets in unions, nested `kid:` references, legacy layout with entities, empty concept body
- [ ] run full suite: `uv run pytest && uv run ruff check src tests && uv run mypy`
- [ ] `grep -rn "\.knott/schemas\|relations:\|attributes:" src docs SPEC.md README.md` finds only migration/legacy mentions
- [ ] `knott view` on `docs/` renders edges correctly (open once by hand)

### Task 11: [Final] Update documentation
- [ ] update README.md if anything changed during implementation
- [ ] add a CLAUDE.md note if new patterns came up (e.g. `iter_references` as the single edge walker)
- [ ] move this plan to `docs/plans/completed/`

## Post-Completion
*Items requiring manual intervention or external systems - no checkboxes, informational only*

**Release**
- bump to v0.5.0 and release per `RELEASING.md`; release notes lead with "breaking: run `knott migrate`".

**External vaults**
- run `knott migrate` in each vault (e.g. the podcast and language-learning vaults behind issues #1 and #3), review the generated `list` vs single choices, and add body templates.
- close #1 (union targets) once released; comment on #9 that relation definitions (0010 §7) build on it.
