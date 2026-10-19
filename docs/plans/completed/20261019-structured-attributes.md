# Add list and structured attributes (#3)

## Overview
- A schema can declare **lists**, **objects** with named fields, and **maps** with free string keys and typed values, nested to any depth. Validation checks every nested value and reports the exact location (`senses[1].ru`, `forms.sg.acc`) with its line.
- Problem: today attributes are scalars only. Richer data (senses, inflection tables, annotations) has to stay undeclared, and undeclared keys are never checked, so mistakes in the most important data pass silently.
- Motivating case: a `lexeme` in a language-learning vault:
  ```yaml
  senses:
    - {id: friend, ru: друг}
  forms:
    sg: {nom: draũgas, gen: draũgo, acc: draũgą}
  ```
- Designed in a grilling session on 2026-10-19 (decisions below). Builds the type model that #4 (enums) and #9 (read API / export) build on.

## Context (from discovery)
- `src/knott/schema/models.py`: `AttributeDef.type` is a flat `ScalarType`. This becomes a recursive shape.
- `src/knott/schema/loader.py`: `_SchemaParser._parse_attributes` parses one level. `_check_keys`, `_required_flag`, `_optional_str` and `error(code, key_path, …)` already take nested key paths, so nested schema errors get exact lines for free.
- `src/knott/schema/validator.py`: `_check_attribute` → `type_mismatch(ScalarType, value, raw)`. `is_absent` / `is_absent_relation` encode decision 0005.
- `src/knott/_yaml.py`: `load()` already records a `Loc(line, raw)` for **every** nested key path, e.g. `("senses", 1, "ru")`.
- `src/knott/vault/entity.py`: `MarkdownFile` keeps only `key_lines` (top level), `item_lines` (top-level list items) and `raw` (top-level scalars). Nested lines and raw text must be kept too.
- `src/knott/models.py`: public `OntologyAttribute(name, type: str, required, description)`. `src/knott/api.py` `Knott.ontology()` builds it.
- `src/knott/cli.py` `types --verbose`: prints only path and description, built from `vault.schemas()` (`SchemaInfo`). It lists no attributes or relations today.
- `src/knott/_view/ontology.html`: the side panel renders attributes as a flat table (`row(esc(a.name), esc(a.type), …)`).
- Decisions: 0004 (strict typing, boolean spelling via raw text), 0005 (empty values).
- Tests: `tests/test_schemas.py`, `tests/test_attributes.py`, `tests/test_api.py`, `tests/test_cli.py`, `tests/test_view.py`, fixtures in `tests/fixtures/<case>/`.

## Decisions (grilling session, 2026-10-19)
1. **Syntax**: explicit keywords, a single form. `type: list` + `items`, `type: object` + `fields`, `type: map` + `values`. Object fields use the same `type`/`required`/`description` definition as top-level attributes. No depth limit (the YAML loader's 100k-node cap already guards). No string shorthand.
2. **Objects are closed**: an undeclared key inside a declared object gives the new issue `attribute-unknown-field`, which lists the allowed fields and suggests "did you mean …" (`difflib`) when one is close. `map` is the open form.
3. **Empty values** (amends 0005): `null`/`""` count as absent at every level. An empty container of the *declared* kind (`[]` for a list, `{}` for an object or map) counts as absent, so a `required` list needs at least one item. An empty container of the wrong kind is a type mismatch (`title: []` stays a mismatch). A list item or map value is never absent: `[a, null]` and `{nom: ~}` are errors.
4. **No relations inside structured values** in #3. Nested references wait for #2/#9.
5. **Map keys** are strings. A non-string YAML key (`1:`, unquoted `yes:`) is reported with a "quote it" hint. No key restriction here; a known set of keys becomes `keys:` with an enum in #4.
6. **No min/max item counts** yet (can be added later as `min_items`/`max_items` without breaking anything).
7. **Inline shapes only**: no named, reusable shapes. That is decided together with #4's reusable value sets.
8. **Issue codes**: nested problems reuse `attribute-missing` and `attribute-type-mismatch`, with `field` set to the full path (`senses[1].ru`, `forms.sg.acc`) and `line` set to the nested key or item.
9. **Schema loader rejects** (`schema-invalid-field`, at the exact key): `list` without `items`, `map` without `values`, `object` without `fields` or with empty `fields`; `items`/`fields`/`values` on the wrong kind; `required` on `items`/`values`. `description` is allowed on `items`/`values`.
10. **`type` is allowed as a nested field name.** It is reserved only at the top level.
11. **Public API**: `OntologyAttribute` mirrors the schema recursively. `type` is a scalar name or `list`/`object`/`map`. It gains `items: OntologyAttribute | None`, `values: OntologyAttribute | None` and `fields: list[OntologyAttribute]`. Item and value nodes have `name=None`. Scalars look the same as today.
12. **Display**: `types --verbose` and `view` use one compact notation: `list of object`, `map of map of string`, with object fields indented below and `*` for required. `types --verbose` also starts listing attributes and relations (`includes → lexeme`).
13. **Reporting**: report every nested problem, but don't descend into a value whose kind is already wrong (`senses: "friend"` gives one mismatch).
14. **Docs**: new decision `0008-structured-attributes`. Amend 0005's table with a note on the change. Update `concepts/attribute.md`, `guides/writing-schemas.md`, `SPEC.md` and the agent `SKILL.md` with a `lexeme` example.

## Development Approach
- **testing approach**: Regular (code first, then tests)
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
  - write unit tests for new and modified functions
  - cover both success and error scenarios
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- maintain backward compatibility: existing scalar schemas, issue codes, messages and `--format json` output stay unchanged

## Testing Strategy
- **unit tests**: `tests/test_schemas.py` (loader), `tests/test_entities.py` (nested lines/raw), `tests/test_attributes.py` (validation), `tests/test_api.py` (`ontology()`), `tests/test_cli.py` (`types --verbose`), `tests/test_view.py` (rendered data).
- New fixture `tests/fixtures/structured-attributes/` with a `lexeme` schema and valid/invalid entities.
- `view` panel layout is checked by hand with a headless Chrome screenshot of a vault with nested shapes.
- Check command: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy`

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix

## Solution Overview
- **One recursive shape.** `AttributeDef` keeps `name`, `required`, `description` and gets a `shape`. A shape is a scalar (`ScalarType`), `ListShape(items)`, `ObjectShape(fields: dict[str, AttributeDef])` or `MapShape(values)`. Item/value nodes are `AttributeDef`s with no name and `required=False`, so `description` works everywhere.
- **Loader recursion.** `_parse_attributes` delegates to a `_parse_definition(definition, key_path, allow_required)` that recurses into `items`/`fields`/`values`, with allowed keys depending on the kind.
- **Validator recursion.** `_check_value(shape, value, path, field)` walks value and shape together and yields issues. It uses `entity.loc(path)` for the line and raw text and stops descending on a kind mismatch. `type_mismatch` stays the scalar check.
- **Nested locations on `MarkdownFile`.** Store the full `locs` map (vault-file 1-based lines + raw), and derive `key_lines`/`item_lines`/`raw` from it so existing callers keep working.
- **Field path formatting** in one helper: `("senses", 1, "ru")` → `senses[1].ru`.

## Technical Details

**Schema example** (from decision 1):
```yaml
type: lexeme
attributes:
  tags:
    type: list
    items: {type: string}
  senses:
    type: list
    required: true
    items:
      type: object
      description: One sense per meaning.
      fields:
        id: {type: string, required: true}
        ru: {type: string, required: true, description: Russian gloss}
  forms:
    type: map
    values:
      type: map
      values: {type: string}
```

**Allowed definition keys by kind**:
| kind | keys |
|---|---|
| scalar | `type`, `required`*, `description` |
| `list` | `type`, `required`*, `description`, `items` (required) |
| `object` | `type`, `required`*, `description`, `fields` (required, non-empty) |
| `map` | `type`, `required`*, `description`, `values` (required) |

\* `required` is not allowed on `items`/`values` nodes.

**Absent / mismatch rule** (decision 3), per value `v` against shape `s`:
- `v is None or v == ""` → absent
- `v == []` and `s` is a list → absent. `v == {}` and `s` is an object/map → absent
- an empty container of another kind → `attribute-type-mismatch`
- absent and required → `attribute-missing` (field path + line). Absent as a list item / map value → `attribute-type-mismatch` ("item must not be empty")

**Example messages**:
```
attribute `senses[1].ru` expects string but got integer `5`; quote the value (e.g. "5") to make it a string
required attribute `senses[0].id` (string) is missing or empty
unknown field `senses[0].rus`; allowed fields: id, ru; did you mean `ru`?
attribute `forms` map key `1` must be a string; quote it (e.g. "1")
```

**Public model** (`src/knott/models.py`):
```python
class OntologyAttribute(_Frozen):
    name: str | None          # None for items/values nodes
    type: str                 # scalar name, or "list" / "object" / "map"
    required: bool
    description: str | None
    items: OntologyAttribute | None = None
    values: OntologyAttribute | None = None
    fields: list[OntologyAttribute] = []
```

**Compact notation** (one helper, shared by CLI and view data):
`list of string`, `list of object`, `map of map of string`, `object`.

## What Goes Where
- **Implementation Steps**: schema model + loader, nested locations, validator, API + display, docs.
- **Post-Completion**: a manual look at `view` with nested shapes; follow-ups for #4 and #9.

## Implementation Steps

### Task 1: Recursive shape model and schema loader

**Files:**
- Modify: `src/knott/schema/models.py`
- Modify: `src/knott/schema/loader.py`
- Modify: `src/knott/schema/validator.py` (adapt to `shape` for scalars only, so tests stay green)
- Modify: `src/knott/api.py` (adapt `ontology()` to the new field, scalars only for now)
- Modify: `tests/test_schemas.py`

- [x] add `ListShape`, `ObjectShape`, `MapShape` and `Shape = ScalarType | ListShape | ObjectShape | MapShape`. Change `AttributeDef.type` to `shape: Shape` and make `name` optional for item/value nodes
- [x] implement `_parse_definition` recursion with per-kind allowed keys; `type` allowed as a nested field name, non-string nested field names rejected
- [x] reject: missing `items`/`values`/`fields`, empty `fields`, nesting keys on the wrong kind, `required` on `items`/`values` (`schema-invalid-field`, exact key path and line)
- [x] update the "unknown attribute type" message to list scalar types plus `list`, `object`, `map`
- [x] write tests: the full `lexeme` schema loads into the expected shape tree; three-level nesting; `description` on `items`
- [x] write tests: each rejection reports the right `field` and line; existing scalar schemas load unchanged
- [x] run tests - must pass before next task

### Task 2: Nested locations on `MarkdownFile`

**Files:**
- Modify: `src/knott/vault/entity.py`
- Modify: `tests/test_entities.py`

- [x] keep a `locs: dict[KeyPath, Loc]` with file lines (offset applied) and raw text for every nested path; add `line_of(path)` / `raw_of(path)` helpers
- [x] derive the existing `key_lines`, `item_lines` and `raw` from it, so callers are unchanged
- [x] write tests: the line and raw text of `("senses", 1, "ru")`, of a map value, and of a flow-style `{id: friend}` item; an aliased nested value gets metadata
- [x] run tests - must pass before next task

### Task 3: Recursive validation

**Files:**
- Modify: `src/knott/schema/validator.py`
- Create: `tests/fixtures/structured-attributes/` (schema + valid and invalid entities)
- Modify: `tests/test_attributes.py`

- [x] add a `format_field_path` helper (`("senses", 1, "ru")` → `senses[1].ru`)
- [x] implement `_check_value` recursion: scalars via `type_mismatch` with the nested raw text (0004 boolean spelling applies); lists per item; objects per declared field plus unknown keys; maps with string keys and per value
- [x] apply the absent/mismatch rule (decision 3) at every level; required fields and lists produce `attribute-missing`
- [x] add `attribute-unknown-field` with the allowed list and a `difflib` suggestion
- [x] stop descending on a kind mismatch; report all other problems
- [x] write tests: the valid `lexeme` passes; `senses[1].ru` wrong type; missing required nested field; `required` list given `[]`; `tags: {}` mismatch; `[a, null]` item error; `{nom: ~}` value error; `rus` → did you mean `ru`; a non-string map key; nested `yes` for a boolean field; `senses: "friend"` gives exactly one issue; lines point at nested keys
- [x] write tests: existing scalar validation and messages are unchanged (`wrong-attribute-type`, `missing-required-field` fixtures)
- [x] run tests - must pass before next task

### Task 4: Public model, `types --verbose` and `view`

**Files:**
- Modify: `src/knott/models.py`
- Modify: `src/knott/api.py`
- Modify: `src/knott/cli.py`
- Modify: `src/knott/_view/ontology.html`
- Modify: `tests/test_api.py`, `tests/test_cli.py`, `tests/test_view.py`

- [x] extend `OntologyAttribute` recursively (`name: str | None`, `items`, `values`, `fields`); build it from the shape tree in `ontology()`
- [x] add the compact notation helper (`list of object`, `map of map of string`)
- [x] `types --verbose`: build from `ontology()`; print attributes (name, `*` for required, notation, description) with object fields indented, then relations (`name* → target`)
- [x] `view` panel: show the notation and indent nested object fields under their attribute
- [x] write tests: `ontology()` returns the nested tree for the fixture and unchanged output for scalar attributes; JSON round-trip
- [x] write tests: `types --verbose` output for the fixture (golden text); `types` without `--verbose` is unchanged
- [x] write test: rendered view data contains the nested fields
- [x] run tests - must pass before next task

### Task 5: Documentation and decision records

**Files:**
- Create: `docs/decisions/0008-structured-attributes.md`
- Create: `docs/issues/attribute-unknown-field.md`
- Modify: `docs/decisions/0005-empty-values.md`
- Modify: `docs/concepts/attribute.md`, `docs/guides/writing-schemas.md`, `docs/commands/types.md`
- Modify: `SPEC.md`, `README.md` (if it shows schema syntax), `src/knott/_skills/knott/SKILL.md`

- [x] write 0008: syntax, closed objects, string map keys, no nested relations, inline shapes only, reasons
- [x] amend 0005: add `{}` and the "empty of its own kind" rule to the table, with a dated note on the change
- [x] document `attribute-unknown-field` like the other issue pages
- [x] update SPEC §7/§8 tables and the validation list; add the `lexeme` example to the guide and the agent skill; describe the new `types --verbose` output
- [x] run `uv run knott validate` inside `docs/` - must pass
- [x] run tests - must pass before next task

### Task 6: Verify acceptance criteria
- [x] every "Expected behavior" and "Requirements" bullet of #3 is covered by a test or doc
- [x] headless Chrome screenshot of `knott view` on the fixture vault (light and dark): nested fields are readable
- [x] run the full check: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy`

### Task 7: [Final] Update documentation
- [x] update README.md if needed
- [x] move this plan to `docs/plans/completed/`

## Post-Completion
*Items requiring manual intervention or external systems - no checkboxes, informational only*

**Manual verification**:
- open a vault with a `lexeme` in Obsidian and check how nested properties display and stay editable

**Follow-ups**:
- #4 enums: add allowed values on scalar shapes (including list items and object fields), `keys:` for maps, and decide reusable definitions together with named shapes
- #9 export: serialize typed nested values using this shape tree
- release as 0.4.0 (additive public API)
