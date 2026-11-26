---
type: command
title: knott list
synopsis: knott list [TYPE] [--where KEY=VALUE]... [--fields KEY,...] [--format text|json]
writes_files: false
concepts:
  - "[Entity](../concepts/entity.md)"
  - "[Attribute](../concepts/attribute.md)"
  - "[Relation](../concepts/relation.md)"
---
# knott list

Lists entities: all of them, or those of one type, filtered by property values. Use it instead of `grep` to answer "which entities have this value": it knows subtypes, reads YAML values rather than text, looks inside lists, and matches a reference by the entity it points at.

```
$ knott list spec --where released_in=0.12.0 --fields status,title
specs/0013-concept-inheritance.md     spec  implemented  0013: Concept inheritance
specs/0014-open-reference-targets.md  spec  implemented  0014: Open reference targets
```

`list` does not validate. Schema issues don't stop it, and an entity with invalid values is listed like any other. A file whose frontmatter cannot be read is skipped.

## The type

- `knott list` lists every entity, ordered by path.
- `knott list TYPE` lists the entities of `TYPE` and of its [subtypes](../concepts/schema.md#inheritance). An abstract type is allowed. Each line shows the entity's own type.
- A `TYPE` no concept defines is an error that names the known types.

## Filters

`--where KEY=VALUE` keeps the entities whose property `KEY` equals `VALUE`. Give it several times to combine conditions; an entity must pass all of them. It needs `TYPE`, and `KEY` must be a top-level property of `TYPE`, its own or inherited. To filter by a property only a subtype declares, name that subtype.

The text is split at the first `=`, and `VALUE` is read by the declared type of `KEY`:

| Type of `KEY` | `VALUE` | Matches when |
|---|---|---|
| `string` | the text, never interpreted: `code=42` is the string `"42"` | the value is that string |
| `integer` | `3`, `-12` | the value is that integer, not `3.0` or `"3"` |
| `number` | `3`, `2.5` | the value is a number equal to it |
| `boolean` | `true` or `false` | the value is that boolean |
| `date` | `2026-10-06` | the value is that date |
| `datetime` | `2026-10-06T09:30:00`, with an offset if the value has one | the value is that moment |
| `enum` | one of the options, exact case | the value is that option |
| `file` | the text | the value, as written, is that text |
| `reference` | an entity: a path relative to the current directory, or `kid:<uuid>` | the reference resolves to that entity |
| `list` of any of these | as for the items | any item matches |

- **A `VALUE` that cannot be read is an error**, not an empty result: `--where status=drafted` lists the options of `status`, `--where count=many` says an integer was expected, and a reference that is not an entity is rejected.
- **A reference matches by its target**, whatever form the file uses: a plain path, a Markdown link or `kid:`. A reference that does not resolve matches nothing.
- **An empty `VALUE`** (`--where released_in=`) keeps the entities where the property is absent: missing, `null`, `""`, or an empty list. This works for every type of property.
- **Objects and maps** cannot be filtered by a value, and neither can a list of them.
- **A value of the wrong kind** (a string where an integer is declared) matches nothing.

```
$ knott list decision --where affects=concepts/relation.md
decisions/0002-relative-paths-not-ids.md                  decision
decisions/0003-source-side-relations.md                   decision
…
```

## Output

One line per entity: its path, its type, then each field of `--fields`, in columns. No match prints `no entities`.

`--fields a,b,c` adds frontmatter keys to the output, in that order. A key does not have to be declared; an entity without it shows `-`. `path`, `type` and `kid` are always in the output and are not accepted as field names.

| Value | Printed as |
|---|---|
| a string | as is, with line breaks replaced by a space |
| a number, boolean, date or datetime | `3`, `true`, `2026-10-06` |
| a list or mapping | JSON on one line: `["red", "blue"]` |
| missing, `null` or `""` | `-` |

`--format json` prints the same entities. `properties` is there only with `--fields`:

```json
{
  "entities": [
    {"path": "specs/0013-concept-inheritance.md", "type": "spec", "kid": null,
     "properties": {"status": "implemented", "title": "0013: Concept inheritance"}}
  ]
}
```

Values are as written in the file: nothing is converted to the declared type, a reference stays the text in the file, a date is `"2026-10-06"`, and a missing or blank value is `null`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success, including no match |
| `1` | the vault still has `.knott/schemas/`: the [`schema-legacy-layout`](../issues/schema-legacy-layout.md) issue goes to stderr |
| `2` | no vault, an unknown `TYPE`, `--where` without `TYPE`, a `KEY` that is not a property of `TYPE`, a missing `=`, a property that cannot be filtered, a `VALUE` that cannot be read, or a bad `--fields` name |

To see one entity in full, with its links resolved, use [`knott show`](show.md).
