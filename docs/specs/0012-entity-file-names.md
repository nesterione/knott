---
type: spec
title: "0012: Entity file names"
status: implemented
created_on: 2026-11-25
released_in: "0.11.0"
realizes:
  - "[Entity file names](../intents/entity-file-names.md)"
decisions:
  - "[0002](../decisions/0002-relative-paths-not-ids.md)"
  - "[0010](../decisions/0010-concept-files-and-reference-properties.md)"
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Entity](../concepts/entity.md)"
amends:
  - "[0005](0005-concept-files.md)"
---
# 0012: Entity file names

## Summary

A concept can declare `filename`: a pattern that the names of its entity files must match. The pattern is literal text with named `{parts}`. Each part can carry a regular expression, which knott checks, and a description, which tells the agent that creates the file how to fill it. `knott validate` reports a name that does not match. Knott never generates or changes a name. The change is additive and independent of [0011](0011-entity-location.md).

## Behaviour

### The `filename` key

```yaml
# .knott/concepts/spec.md
---
name: spec
filename:
  pattern: "{number}-{slug}"
  parts:
    number:
      match: "[0-9]{4}"
      description: The next free number in specs/.
    slug:
      match: "[a-z0-9]+(-[a-z0-9]+)*"
      description: What the change does, in two to five lowercase words.
---
```

`filename` is a top-level key of a concept file, a mapping with closed keys:

| Key | Required | Value |
|---|---|---|
| `pattern` | yes | a non-empty string: literal text and `{part}` placeholders |
| `parts` | when `pattern` has placeholders | part name → a mapping with `match` and `description`, both optional; or empty |

- The pattern describes the file name **without** `.md`. The folder is never part of the match.
- **Literal text** is matched exactly. `.`, `-`, `(` and the like have no special meaning there, so nothing is escaped. A literal `{` or `}` cannot be written.
- **A part** is `{name}`, with `name` matching `^[a-z][a-z0-9_]*$`. A part may be used once. Every part in `pattern` is defined in `parts`, and every key of `parts` is used in `pattern`.
- **`match`** is a regular expression in Python `re` syntax that the part must match in full. Without it the part is any non-empty text. Each part is matched on its own, so groups, flags and anchors in one `match` do not reach another.
- **`description`** is a string for the reader who names the file, human or agent: where the value comes from and how to form it. Knott shows it and never interprets it.
- A pattern with no parts is a fixed name (`pattern: index`).
- Quote `pattern` and `match` (`pattern: "{slug}"`, `match: "[0-9]{4}"`): YAML reads an unquoted leading `{` as a mapping and `[` as a list, so the value is `schema-invalid-field` or the file is `schema-invalid-yaml`. A part name YAML reads as a boolean (`no`, `on`, `y`) is quoted under `parts` too.

### Matching

- The name matches when the whole of it can be split into the literal text and the parts, each part matching its `match`. Knott checks only that a split exists; it does not extract the parts or compare them with anything.
- Matching regards case. The name is compared in Unicode NFC, so a macOS file system does not change the result.

### Checks on `filename`

Each of these is `schema-invalid-field` at its line, with the key path as `field` (`filename.parts.slug.match`). An empty `filename:` is the same as no key. The concept still loads, without `filename`:

- a value that is not a mapping, an unknown key (with a "did you mean" suggestion), a missing or empty `pattern`;
- a `/` or `\` in the literal text; an unclosed, empty or invalid `{…}`; the same part twice;
- a part in `pattern` that `parts` does not define, or a key of `parts` that `pattern` does not use;
- a `match` that is not a string, does not compile, or can match the empty string;
- a `description` that is not a string.

## Issue codes

| Code | Stage | When | `field` / `line` |
|---|---|---|---|
| `entity-invalid-name` | entity | the entity's type declares `filename` and the file name does not match | none / the line of `type` |

```
✗ specs/loops.md:2
  `spec` files are named `{number}-{slug}.md` (number: `[0-9]{4}`, slug: `[a-z0-9]+(-[a-z0-9]+)*`), but this one is `loops.md`
```

`.md` is added for display. Parts without `match` are left out of the parentheses. Descriptions are not printed; `knott types --verbose` shows them.

## CLI and API

- `knott validate`: reports `entity-invalid-name` like any other error. An entity can have both this and `entity-misplaced`.
- `knott types --verbose`: after `template:` (and `path:`), the pattern and one line per part:

  ```
  spec  (.knott/concepts/spec.md)
    template: yes
    filename: {number}-{slug}.md
      number  [0-9]{4}                The next free number in specs/.
      slug    [a-z0-9]+(-[a-z0-9]+)*  What the change does, in two to five lowercase words.
  ```

- `knott view`: the type's panel shows the same.
- Python API: `OntologyType.filename: FilenamePattern | None`, with `FilenamePattern(pattern: str, parts: list[FilenamePart])` and `FilenamePart(name: str, match: str | None, description: str | None)`, both exported from `knott`.
- Agent skill: before creating an entity, read `filename`; fill each part as its description says, and check the result against `match`.

## Edge cases

| Case | Result |
|---|---|
| `specs/0011-Entity-Location.md` | `entity-invalid-name`: `slug` allows lowercase only |
| `specs/0011-.md` | `entity-invalid-name`: a part is never empty |
| `pattern: "{a}-{b}"`, no `match`, file `x-y-z.md` | valid: some split exists |
| `pattern: "{slug}.md"` | valid, but it requires a file named `….md.md` |
| `match: "^[0-9]{4}$"` or `(?i)[a-z]+` | valid; anchors and flags stay inside the part |
| `pattern: {slug}`, unquoted | `schema-invalid-field`: YAML read a mapping; the message says to quote it |
| `match: [0-9]{4}`, unquoted | `schema-invalid-yaml`; quote it |
| `knott validate specs/0012-X.md`, the file on disk is `0012-x.md` | `entity-invalid-name`: a path argument is taken as written; pass it as it is on disk |
| `match: "[0-9]*"` | `schema-invalid-field`: it can match the empty string |
| Renaming a file to fix the issue | links to it in other files break and are reported as `relation-target-not-found` |

## Out of scope

- A part bound to a property (`{created_on}` must equal the property's value), and a part bound to the folder.
- Parts that knott fills: the next free number, a slug made from `title`, and any call to a language model. Knott publishes the description; the agent does the naming.
- Named part kinds (`slug`, `date`) so `match` need not be repeated across concepts.
- Uniqueness of a part across the type, such as two specs with one number.
- Renaming a file and rewriting the links that point at it ([0002](../decisions/0002-relative-paths-not-ids.md)).
- A time limit on `match`. An expression such as `(a+)+b` can be slow on a name that does not fit. [Decision 0007](../decisions/0007-parser-robustness.md) bounds YAML, not expressions the vault owner writes; a bound here would need its own decision.

## Compatibility

Additive. A concept with a `filename` key got `schema-invalid-field` before. Adding `filename` to a concept makes entities with other names invalid; `knott validate` lists them. Ontology API additions only. Version 0.11.0.
