# Add knott-managed `kid` identity (#2)

## Overview
- Every entity can carry a knott-managed identity: `kid: <lowercase UUID>`, a reserved top-level frontmatter key like `type`.
- Relations can refer to an entity as `kid:<uuid>` as well as by path. Markdown links stay the default and recommended form.
- `knott validate --fix` inserts a missing `kid` (UUIDv4) as a one-line text edit. It is knott's only edit to user files.
- Designed in a brainstorm session on 2026-10-20..22 (decisions below).

## Decisions
1. Key `kid`, owned by knott on every entity. Schemas may not declare a field named `kid` (nested object fields may).
2. Value: canonical lowercase UUID (`8-4-4-4-12` hex), any version. Knott generates v4. Uppercase / `{…}` forms are rejected with the lowercase form suggested.
3. Optional by default. A schema opts in with top-level `kid: required` (the only accepted value).
4. Uniqueness is global. A duplicate is reported once (`kid-duplicate`) on the first claimant by path, listing every `path:line`. `--fix` never touches duplicates.
5. References: `kid:<uuid>`, plain only (`[x](kid:…)` rejected). Resolution stays behind `resolve_reference()`. Then the usual entity and type checks run. Ambiguous `kid` → `relation-target-ambiguous`.
6. The index (`kid → claimants`) is built lazily, once per run, only when an in-scope entity has a `kid` or a relation uses `kid:`. Scoped runs report a duplicate only if a claimant is in scope.
7. `--fix`: for in-scope entities with no `kid` key at all, insert `kid: <uuid4>` after a single-line `type:` (else before the closing `---`), keep line endings / BOM, write atomically, re-parse to verify, then re-validate. The result has `fixed: [{path, kid}]`.
8. New codes: `kid-missing`, `kid-invalid`, `kid-duplicate`, `relation-target-ambiguous`.
9. `OntologyType.kid_required`; `types --verbose` prints `kid: required`; the view subtitle shows it.
10. Docs: decision 0009, 0002 amended, `concepts/kid.md`, issue pages, SPEC, README, skill.

Out of scope (follow-up issues): natural-key uniqueness (`unique: true`) to catch duplicate concepts; `knott create` (always writes a `kid`); find-by-kid lookup (#9).

## Tasks

### Task 1: Schema `kid: required` and reserved field name
- [x] `Schema.kid_required`; top-level `kid` key accepts only `required`
- [x] top-level field named `kid` → `schema-field-conflict`
- [x] tests

### Task 2: `kid` checks and index
- [x] `vault/kid.py`: canonical check, suggestion, `KidIndex` (claimants by kid)
- [x] validator: `kid-missing` / `kid-invalid` per entity
- [x] api: lazy index, scoped `kid-duplicate`
- [x] tests with a fixture vault

### Task 3: `kid:` references
- [x] `parse_reference` / `resolve_reference` handle `kid:`; reject `[x](kid:…)`
- [x] not found / ambiguous / type mismatch messages
- [x] tests, including a moved target

### Task 4: `validate --fix`
- [x] text insert with line endings, BOM, atomic write, re-parse check
- [x] `ValidationResult.fixed`, `validate(fix=True)`, CLI `--fix` text and JSON output
- [x] tests: byte-identical apart from the line, CRLF, BOM, idempotent, refused edit

### Task 5: Ontology and display
- [x] `OntologyType.kid_required`; `types --verbose`; view subtitle
- [x] tests

### Task 6: Docs
- [x] decision 0009, amend 0002, `concepts/kid.md`, four issue pages, reference resolution, SPEC, README, skill, docs index
- [x] `knott validate` inside `docs/` passes

### Task 7: Final
- [x] full check: `uv run pytest && uv run ruff check . && uv run ruff format --check src tests && uv run mypy`
- [x] move this plan to `docs/plans/completed/`
