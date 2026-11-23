---
type: spec
title: "0004: Give entities a knott-managed `kid`"
status: implemented
created_on: 2026-10-22
released_in: "0.4.0"
github_issues:
  - 2
decisions:
  - "[0009](../decisions/0009-kid-identity.md)"
  - "[0002](../decisions/0002-relative-paths-not-ids.md)"
concepts:
  - "[Kid](../concepts/kid.md)"
  - "[Entity](../concepts/entity.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
---
# 0004: Give entities a knott-managed `kid`

## Summary

Every entity can carry `kid: <lowercase UUID>`, an identity that survives moves and renames. Relations can refer to an entity as `kid:<uuid>` as well as by path. `knott validate --fix` adds a missing `kid` as a one-line edit, knott's only edit to user files. Vaults without `kid`s behave as before.

## Behaviour

### The `kid` key

```yaml
---
type: lexeme
kid: 3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21
lemma: draugas
---
```

- `kid` is a reserved top-level frontmatter key, owned by knott on every entity, like `type`.
- The value is a canonical lowercase UUID: `8-4-4-4-12` hex digits, any version. Knott generates v4. Uppercase, `{…}` and other spellings are `kid-invalid`; when the value parses as a UUID, the message gives the canonical form.
- A present `kid` is always checked, whether or not the schema requires one.
- **Optional** by default. A schema opts in with top-level `kid: required`, the only accepted value. Then an entity with no `kid`, or an empty one, is `kid-missing`.
- **Unique** across the vault, whatever the type. A value claimed by several entities is reported once, as `kid-duplicate` on the first claimant by path, listing every claimant as `path:line`.

### Schemas

- Top-level `kid: required` makes the key required for that type. Any other value is `schema-invalid-field`: ``` `kid` must be `required`, got `true`; omit it to make `kid` optional ```.
- A schema can't declare a top-level attribute or relation named `kid`: `schema-field-conflict`, ``a field cannot be named `kid`; it is reserved for the knott-managed entity identity``. A field inside an `object` may be called `kid`.

### `kid:` references

```yaml
includes:
  - "[Draugas](../lexemes/draugas.md)"            # default: a Markdown link
  - kid:3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21      # survives moves and renames
```

- Any relation value may be `kid:<uuid>`. Markdown links stay the default and recommended form.
- It must be written on its own. `[x](kid:…)` is `relation-invalid-value`.
- Resolution stays behind `resolve_reference()`: the `kid` is looked up in the index, then the usual entity and target-type checks run.

| Case | Result |
|---|---|
| the value after `kid:` is not a canonical UUID | `relation-invalid-value` |
| no entity has that `kid` | `relation-target-not-found`: ``no entity has `kid` <uuid>`` |
| several entities claim it | `relation-target-ambiguous`, naming the claimants |
| one entity claims it | type check as for a path |

### The index

The `kid` → claimants index is built lazily, at most once per run, only when an in-scope entity has a `kid` or a relation uses `kid:`. Only valid `kid`s are indexed. It covers the whole vault, so a scoped run (`knott validate some/file.md`) still finds targets and duplicates outside its scope, but reports a duplicate only when one of its claimants is in scope.

### `validate --fix`

For each in-scope entity with no `kid` key at all:

1. Insert `kid: <uuid4>` after the top-level `type:` line when it is a single line, otherwise before the closing `---`.
2. Keep the file's line endings (LF or CRLF) and BOM. Everything else stays byte-for-byte the same.
3. Re-parse the result. It is written only if the frontmatter equals the old one plus the new `kid`; otherwise the file is left alone.
4. Write atomically (temp file in the same folder, then rename), keeping the file mode.
5. Then validate as usual.

`--fix` never touches an existing `kid`, even an empty, invalid or duplicated one. It skips files that aren't entities, have invalid frontmatter, or resolve outside the vault. Without `--fix`, `validate` never writes.

### Display

- `OntologyType.kid_required` is true when the schema says `kid: required`.
- `knott types --verbose` prints `kid: required` under the type's description.
- In `knott view`, the panel subtitle reads `N entities · kid required`.

## Issue codes

| Code | Stage | When | `field` | `line` |
|---|---|---|---|---|
| `kid-missing` | kid | schema says `kid: required`; `kid` is absent or empty | `kid` | the `kid:` line, else the `type:` line |
| `kid-invalid` | kid | `kid` is present but not a canonical lowercase UUID | `kid` | the `kid:` line |
| `kid-duplicate` | kid | two or more entities claim one `kid`; reported once, on the first by path | `kid` | the first claimant's `kid:` line |
| `relation-target-ambiguous` | relation | a `kid:` reference names a duplicated `kid` | the relation | the reference |
| `schema-invalid-field` (changed) | schema | `kid` set to anything but `required` | `kid` | that key |
| `schema-field-conflict` (changed) | schema | a top-level field named `kid` | the field | that key |

```
✗ lexemes/bad.md:2  kid
  `lexeme` entities require a `kid`; run `knott validate --fix` to add one

✗ lexemes/bad2.md:3  kid
  `kid` must be a lowercase UUID such as 3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21, got string `3F2B8C1E-9D4A-4C2E-B7F1-0A6D5E9C8B21`; write 3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21

✗ lexemes/dup1.md:3  kid
  `kid` 3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21 is claimed by 2 entities: lexemes/dup1.md:3, lexemes/dup2.md:3
  each entity needs its own `kid`; remove the `kid:` line from the copy, then run `knott validate --fix`

✗ lexemes/amb.md:6  topic
  relation `topic`: `kid` 3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21 is claimed by 2 entities (lexemes/dup1.md:3, lexemes/dup2.md:3); fix the `kid-duplicate` first

✗ lexemes/link.md:6  topic
  relation `topic`: a `kid:` reference cannot be a Markdown link; write `kid:3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21` on its own
```

## CLI and API

```
knott validate [PATHS...] [--fix] [--format text|json]
```

`--fix` lists each changed file before the usual result:

```
$ knott validate --fix lexemes/
+ kid  lexemes/namas.md

✓ 2 schemas
…
```

With `--format json`, the output gains `"fixed": [{"path": …, "kid": …}]` when `--fix` is given. Exit codes are unchanged.

Python:

- `Knott.validate(paths=None, *, fix=False)`. With `fix=True`, `ValidationResult.fixed` lists a `FixedEntity(path, kid)` per inserted `kid`.
- `OntologyType.kid_required: bool`.

## Edge cases

- A copied file: both copies keep the same `kid` and get one `kid-duplicate`. `--fix` changes neither; delete the line from the copy and run `--fix`.
- `kid:` present but empty: `kid-missing` if required, else nothing; `--fix` doesn't fill it, because the key exists.
- `type:` written over several lines: the `kid` goes before the closing `---`.
- A CRLF file with a BOM: the inserted line uses CRLF and the BOM stays.
- Running `--fix` twice: the second run changes nothing.
- A target moved after a `kid:` reference was written: the reference still resolves.
- A `kid:` reference to an entity of the wrong type: `relation-target-type-mismatch`, as for a path.
- An `object` field named `kid`: allowed; only the top level is reserved.

## Out of scope

- Natural-key uniqueness (`unique: true`) to catch two entities describing the same concept; a `kid` doesn't detect that.
- A `knott create` command that always writes a `kid`.
- Find-by-`kid` lookup in the read API (#9).

## Compatibility

Additive. Entities and schemas without `kid` validate as before. The only write is behind `--fix`. A schema field named `kid` at the top level, which was allowed before, is now `schema-field-conflict`. Released in 0.4.0.
