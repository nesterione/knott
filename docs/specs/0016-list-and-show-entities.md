---
type: spec
title: "0016: List and show entities"
status: implemented
created_on: 2026-11-26
released_in: "0.14.0"
realizes:
  - "[Read the vault as data](../intents/read-the-vault-as-data.md)"
decisions:
  - "[0001](../decisions/0001-markdown-is-source-of-truth.md)"
  - "[0003](../decisions/0003-source-side-relations.md)"
  - "[0004](../decisions/0004-strict-typing.md)"
  - "[0005](../decisions/0005-empty-values.md)"
concepts:
  - "[Entity](../concepts/entity.md)"
  - "[Attribute](../concepts/attribute.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
---
# 0016: List and show entities

## Summary

Two read-only commands answer questions about entities. `knott list [TYPE]` lists the entities of a type and its subtypes, filtered by property values, with chosen properties in the output. `knott show PATH` prints one entity's properties, its outgoing references resolved to path, type and `kid`, and its incoming links, without the body unless asked. Both have `--format json` and a Python API. Nothing breaks.

## Behaviour

### Which files are listed

- An entity is a Markdown file in the vault whose frontmatter is a mapping with a `type` key, as for `validate`.
- Neither command validates. Schema issues don't stop them; they work with the concept and relation files that loaded, as `refs` does.
- An entity with invalid values, an unknown type or an abstract type is listed like any other. A file whose frontmatter cannot be read is not an entity and is skipped by `list`.

### The entity record

Both commands describe an entity with the same record:

| Key | Value |
|---|---|
| `path` | vault-relative path, with `/` |
| `type` | the frontmatter `type` as written (a non-string in YAML form, as in `refs`) |
| `kid` | the entity's `kid`, or `null` when it has none or it is invalid |
| `properties` | the frontmatter keys other than `type` and `kid`, in file order |

Values in `properties` are the values as written, converted to JSON:

- A string, integer, number or boolean stays what YAML read. Nothing is coerced to the declared type ([0004](../decisions/0004-strict-typing.md)): a `string` property written `42` is the number `42`.
- A date is `"2026-11-23"`. A datetime is its ISO 8601 form, `"2026-11-23T10:30:00"`, with the offset when one was written.
- A reference or file value stays the text in the file (`"[0005](0005-concept-files.md)"`). Resolved references are reported separately by `show`.
- A null or blank value is `null`. Keys no concept declares are included.
- A value JSON cannot hold is a string in its YAML form: `.nan`, `.inf`, `-.inf`, a binary value, a set. A nested mapping key that is not a string becomes its YAML text (`1`, `true`). A top-level key that is not a string can never name a property and is left out.
- A null or blank value is `null` at any depth, so `[""]` is `[null]`.

### `list`: the type

- `knott list` lists every entity. `knott list TYPE` lists the entities whose type is `TYPE` or one of its subtypes, at any depth. An abstract `TYPE` is allowed and lists its subtypes' entities.
- A `TYPE` no concept defines is a usage error that names the known types. Entities of an undefined type appear only in the unfiltered listing.
- Entities are ordered by path.

### `list`: filters

`--where KEY=VALUE` keeps the entities whose property `KEY` equals `VALUE`. It can be given several times; an entity must pass all of them.

- `--where` needs `TYPE`. `KEY` must be a top-level property of `TYPE`, own or inherited. Any other key is a usage error that lists the properties of `TYPE`. A property only a subtype declares is filtered by naming that subtype.
- The text is split at the first `=`. `VALUE` is read by the declared shape of `KEY`:

  | Shape | `VALUE` | An entity matches when |
  |---|---|---|
  | `string` | the text, never interpreted (`--where code=42` is the string `"42"`) | its value is that string |
  | `integer` | `-?[0-9]+` | its value is that integer (not `3.0`, not `"3"`) |
  | `number` | an integer or a decimal | its value is an integer or float equal to it |
  | `boolean` | `true` or `false` | its value is that boolean |
  | `date` | `YYYY-MM-DD` | its value is that date |
  | `datetime` | ISO 8601 with a time | its value is that moment |
  | `enum` | one of the options, exact case | its value is that option |
  | `file` | the text | its value, as written, is that text |
  | `reference` | an entity: a path relative to the current directory, or `kid:<uuid>` | its reference resolves to that entity |
  | `list` of any shape above | as for the item shape | any item matches |
  | `object`, `map`, a list of them, a list of lists | not allowed | |

- A `VALUE` that cannot be read as the shape (`--where count=many`, an option the enum doesn't list, a path that is not an entity) is a usage error that says what was expected. So a misspelt enum option fails loudly; it does not return an empty list.
- A reference matches by the entity it resolves to, whatever form the file uses (plain path, Markdown link, `kid:`). A reference that does not resolve matches nothing. The target-type check is not applied: a wrong-type reference still points at the entity, as in `refs`.
- An empty `VALUE` (`--where released_in=`) keeps the entities where the property is absent, by the rules of [0005](../decisions/0005-empty-values.md): missing, `null`, `""`, and `[]` for a list. It is allowed for every shape, including `object` and `map` (`{}`).
- An entity whose value has the wrong kind for the property (a string where an integer is declared) matches no non-empty filter on it.

### `list`: output fields

`--fields a,b,c` adds top-level frontmatter keys to the output, in the order given.

- Without `--fields`, the output has `path`, `type` and `kid` only, and `properties` is left out.
- A key does not have to be declared. An entity without the key shows `null`.
- `type`, `kid` and `path` are not accepted as field names; they are always present. An empty name or a repeated name is a usage error.

### `show`: one entity

`show` prints the record with all its properties, then two views of its links:

- **`references`**: every value of a declared reference property, at any depth, in schema order (list items in list order). Each has the `field` path (`realizes[0]`, `speakers[1].person`), the `relation` the property names (or `null`), the `value` as written, the target's `path`, `type` and `kid`, and `error`: `null`, or the issue code `validate` reports for that value.

  | The value | `path` | `type`, `kid` | `error` |
  |---|---|---|---|
  | resolves to an entity of an accepted type | the target | the target's | `null` |
  | resolves to an entity of another type | the target | the target's | `relation-target-type-mismatch` |
  | resolves to a Markdown file that is not an entity (a note, or unreadable frontmatter) | the file | `null` | `relation-target-not-entity` |
  | names no file, or a `kid` no entity has | `null` | `null` | `relation-target-not-found` |
  | leaves the vault | `null` | `null` | `relation-target-outside-vault` |
  | is a `kid` several entities claim | `null` | `null` | `relation-target-ambiguous` |
  | is not a reference (a wikilink, a URL, a malformed `kid`, a non-string) | `null` | `null` | `relation-invalid-value` |

  A property with the wrong cardinality (one value where a list is declared, or a list where one is) gives a single row for the property, with `field` its path without an index, `value` as written and `error: relation-invalid-value`. So does a map of references with a key that is not a string. An empty list item or map value (`- ` with nothing after it) is a row with `value: null` and `error: relation-invalid-value`, since `validate` reports it. An absent property gives no row, required or not. The rows with an error are exactly the `relation-*` issues `validate` reports for the entity, other than `relation-missing`.
- **`referenced_by`**: the groups of `knott refs` for this entity, unchanged ([spec 0006](0006-relation-definitions.md)).

An entity whose type no concept defines has no declared references, so `references` is empty; its incoming links are still listed.

The body is not printed. `--body` adds it verbatim, from the line after the closing `---`; a blank body is `null`.

## CLI and API

### `knott list [TYPE]`

```
knott list [TYPE] [--where KEY=VALUE]... [--fields KEY,...] [--format text|json]
```

```
$ knott list spec --where released_in=0.12.0 --fields status,title
specs/0013-concept-inheritance.md     spec  implemented  0013: Concept inheritance
specs/0014-open-reference-targets.md  spec  implemented  0014: Open reference targets

$ knott list decision --where affects=concepts/relation.md
decisions/0002-relative-paths-not-ids.md   decision
decisions/0003-source-side-relations.md    decision
…
```

- One line per entity: path, type, then each field. Every column but the last is padded to its widest value plus two spaces; lines have no trailing spaces.
- A field value is printed as: a string as is, with line breaks replaced by a space; a number, boolean, date or datetime in its JSON form without quotes; a list or mapping as JSON on one line, with `, ` and `: ` as separators (`["red", "blue"]`); `null` as `-`.
- Field names in `--fields` are trimmed, so `--fields "status, title"` works.
- No match prints `no entities`.
- `--format json`:

  ```json
  {
    "entities": [
      {"path": "specs/0013-concept-inheritance.md", "type": "spec", "kid": null,
       "properties": {"status": "implemented", "title": "0013: Concept inheritance"}}
    ]
  }
  ```

  `properties` is present only with `--fields`. No match is `{"entities": []}`.
- The vault is found from the current directory. A reference `VALUE` is a path relative to the current directory.
- Exit codes: `0` on success, including no match. `1` when the vault has the legacy layout (the `schema-legacy-layout` issue goes to stderr). `2` for no vault, an unknown `TYPE`, `--where` without `TYPE`, a `KEY` that is not a property of `TYPE`, a missing `=`, a shape that cannot be filtered, a `VALUE` that cannot be read, or a bad `--fields` name.

### `knott show PATH`

```
knott show PATH [--body] [--format text|json]
```

`PATH` is an entity file, relative to the current directory, or `kid:<uuid>`, exactly as for `refs`.

```
$ knott show specs/0006-relation-definitions.md
specs/0006-relation-definitions.md  spec

properties
  title        0006: Relation definitions and reverse lookup
  status       implemented
  created_on   2026-11-23
  released_in  0.6.0

references
  realizes[0]   intents/relation-definitions.md                           intent
  decisions[0]  decisions/0010-concept-files-and-reference-properties.md  decision
  decisions[1]  decisions/0003-source-side-relations.md                   decision
  concepts[0]   concepts/relation.md                                      concept
  concepts[1]   concepts/ontology.md                                      concept
  concepts[2]   concepts/schema.md                                        concept
  amends[0]     specs/0005-concept-files.md                               spec      (amends)

referenced by
  amended_by
    specs/0007-view-inline-relations.md   spec  amends[0]
    specs/0013-concept-inheritance.md     spec  amends[1]
    specs/0014-open-reference-targets.md  spec  amends[1]
```

- The header line is the path, two spaces and the type, as in `refs`; a `kid` follows on the same line, after two spaces, as `kid:<uuid>` when the entity has one.
- `properties` lists every top-level key except those whose declared shape is `reference` or a `list` of references, with values printed as in `list`. A property that holds references deeper (`speakers`, a list of objects with a `person` reference) is printed here in full, and its references also appear under `references`. `references` lists the outgoing references: field, target path, target type, then the relation in parentheses when the property names one. An unresolved reference shows its value as written and the error code in place of the path and type. A file that is not an entity shows its path and the error code in place of the type. An entity of the wrong type shows its path and type, and the error code at the end of the line, after the relation. `referenced by` holds the output of `refs` from its first group on, indented by two spaces.
- A section with nothing in it is left out. With `--body`, a `body` section follows, separated by a blank line and printed verbatim, not indented.
- `--format json`:

  ```json
  {
    "entity": {"path": "specs/0006-relation-definitions.md", "type": "spec", "kid": null,
               "properties": {"title": "0006: …", "status": "implemented",
                              "created_on": "2026-11-23",
                              "amends": ["[0005](0005-concept-files.md)"]}},
    "references": [
      {"field": "amends[0]", "relation": "amends", "value": "[0005](0005-concept-files.md)",
       "path": "specs/0005-concept-files.md", "type": "spec", "kid": null, "error": null}
    ],
    "referenced_by": []
  }
  ```

  In JSON, `properties` holds every key, references included. `referenced_by` is the `groups` list of `refs --format json`. `body` is present only with `--body`.
- Exit codes are those of `refs`: `0` on success, `1` for the legacy layout, `2` when `PATH` doesn't exist, is outside the vault, is not an entity, or a `kid:` is malformed or matches no entity or several.

### Python API

- `Knott.entities(type: str | None = None, *, where: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None, fields: Sequence[str] | None = None) -> list[EntityRecord]`. `where` is a mapping, or a sequence of `(key, value)` pairs when one key is given twice. Its values are typed, not text: an `int` for an integer, a `datetime.date` for a date, a path (resolved against the vault root) or `kid:<uuid>` string for a reference, and `None` for "absent". Raises `KnottError` for the exit-2 cases.
- `Knott.show(path_or_kid: str | Path, *, body: bool = False) -> EntityDetail`, with `entity: EntityRecord`, `references: list[OutgoingRef(field, relation, value, path, type, kid, error)]`, `referenced_by: list[RefGroup]` and `body: str | None`. Raises as `Knott.refs` does.
- `EntityRecord(path, type, kid, properties)`. `properties` is `None` from `entities()` without `fields`. Values are Python values (`datetime.date`, not a string); `model_dump(mode="json")` gives the JSON forms above.
- `EntityRecord`, `EntityDetail` and `OutgoingRef` are exported from `knott`.

## Edge cases

| Case | Result |
|---|---|
| `knott list concept`, and `tool` extends `concept` | entities of both; each line shows its own type |
| `knott list page` where `page` is abstract | the entities of its subtypes |
| `knott list --where status=draft` | exit 2: a filter needs a type |
| `knott list spec --where status=drafted` | exit 2: lists the options of `status` |
| `knott list spec --where title=a=b` | matches the title `a=b` |
| `knott list spec --where released_in=` | specs with no `released_in`, or a blank one |
| `knott list tool --where version=2` where only `tool` declares `version`, as a string | matches `version: "2"`, not `version: 2` |
| `knott list concept --where version=2` in that vault | exit 2: `version` is not a property of `concept` |
| `--where affects=concepts/relation.md` and a decision stores the link as `kid:` | it matches |
| `--where affects=README.md` (not an entity) | exit 2 |
| `--where speakers=…` on a list of objects | exit 2: cannot be filtered |
| The same `--where` key twice with different values, on a scalar | no entities; on a list, entities holding both |
| `--fields title` on an entity without `title` | `-` in text, `null` in JSON |
| An entity with `type: 42` | in `knott list` with type `42`; no `TYPE` argument matches it |
| A file that starts with `---` but has broken YAML | skipped by `list`; `show` exits 2 |
| `knott show` on an entity with a reference to a deleted file | listed in `references` with `error: relation-target-not-found` |
| `knott show` on a symmetric link stored by this entity | in `references`, and in its symmetric group of `referenced_by` with direction `out` |
| `knott show --body` on an entity with a blank body | no `body` section; `"body": null` |
| A datetime written with an offset, filtered by the same moment in another offset | it matches; a `VALUE` without an offset never matches a value with one |
| `--where due=2026-10-06` and an entity writes `due: "2026-10-06"` | it matches: a quoted ISO date is a valid date |
| `--where urgent=true` and an entity writes `urgent: yes` | no match: `yes` is not a boolean spelling knott accepts |

## Out of scope

- Comparisons (`<`, `>`, ranges), "or", negation and filters on nested fields. A later spec, when a vault needs them.
- Filters on `path` or on the body, and full-text search: `grep` and globs do that.
- Sorting other than by path, and limits.
- Resolved references in `list` output.
- An export of the whole vault, content fingerprints, and following chains of links; they stay in the [intent](../intents/read-the-vault-as-data.md).
- One type's details from `knott types NAME`: [spec 0017](0017-types-for-one-type.md).
- Any command that writes. Moving a file is [spec 0018](0018-move-entities.md); creating and editing entities are not specified.

## Compatibility

Additive. Two new commands and three new API models; no existing output changes. Version 0.14.0.
