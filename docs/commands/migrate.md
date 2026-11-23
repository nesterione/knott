---
type: command
title: knott migrate
synopsis: knott migrate [PATH]
writes_files: true
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Vault](../concepts/vault.md)"
---
# knott migrate

Converts a vault made before 0.5 to [concept files](../concepts/schema.md). `PATH` is any path inside the vault, default the current directory. Run it when `knott validate` reports [`schema-legacy-layout`](../issues/schema-legacy-layout.md).

For each `.knott/schemas/**/*.yaml` file it writes `.knott/concepts/<same relative path>.md`, then deletes `.knott/schemas/`:

- `type` becomes `name`. `description` and `kid` are kept.
- `attributes` and then `relations` merge into one `properties` map, in file order. Attribute definitions are copied as they are.
- A relation becomes `{type: reference, target: …}`. If any current entity of that type stores a list in that field, it becomes a `list` of references instead, and `required` moves to the list.
- The body (the [template](../concepts/schema.md)) is left empty.

Entities are not changed. Then it validates the vault and prints the result.

```yaml
# .knott/schemas/compilation.yaml
type: compilation
relations:
  sources:
    target: script
    required: true
```

becomes, because an entity already stores a list in `sources`:

```markdown
---
name: compilation
properties:
  sources:
    type: list
    required: true
    items:
      type: reference
      target: script
---
```

## Output

```
$ knott migrate
+ .knott/concepts/compilation.md
+ .knott/concepts/media/episode.md
+ .knott/concepts/script.md
  list of reference: compilation.sources
- .knott/schemas/

✓ 3 schemas
✓ 4 entities
✓ 4 relations
✓ vault is valid
```

`+` lines are the concept files written, `list of reference:` lines are the relations that became lists, and `-` is the folder removed. Review the diff in Git afterwards, and add a body template where it helps.

A relation that stays a single reference now accepts exactly one value. An entity written later with a list there gets `relation-invalid-value`; change the property to a `list` of references if several are meant.

## Refusals

It checks everything before it writes anything. In these cases it prints `error: …`, changes nothing, and exits `2`:

| Case | Message |
|---|---|
| no `.knott/schemas/` folder | ``nothing to migrate: <root> has no `.knott/schemas/` folder`` |
| a schema file is not valid YAML or not UTF-8 | ``.knott/schemas/y.yaml:2: invalid YAML: …`` |
| an unknown key in a schema or a relation | ``.knott/schemas/x.yaml: unknown key `atributes` in schema; allowed keys: …`` |
| a name under both `attributes` and `relations` | ``field `source` is declared both as an attribute and as a relation`` |
| a relation without `target` | ``relation `about` is missing `target` `` |
| the concept file it would write already exists | ``.knott/concepts/script.md already exists; move it away or delete it, …`` |
| a file in `.knott/schemas/` that isn't `.yaml` | ``not a `.yaml` schema; move it out of `.knott/schemas/` first, …`` |
| a file where a folder of a concept file would go | ``.knott/concepts/media is not a folder; move it away or delete it, …`` |
| `.knott/schemas/` is a symbolic link | `` `.knott/schemas/` is a symbolic link; replace it with a real folder first, … `` |
| writing a concept file fails (disk full, no permission) | ``cannot write concept files: .knott/concepts/script.md: No space left on device; nothing was changed`` |

When a write fails, the concept files and folders written so far are removed again. Hidden files such as `.DS_Store` are deleted with the folder. Fix the problem and run it again.

If every concept file is written but `.knott/schemas/` can't be deleted, it prints ``error: concept files written, but `.knott/schemas/` could not be removed: …; delete `.knott/schemas/` by hand`` and exits `2`. The concept files are complete and kept, because the delete may have removed some legacy files already. Delete `.knott/schemas/` yourself, then run `knott validate`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | migrated, and the vault is valid |
| `1` | migrated, but the vault has validation issues (printed as by `knott validate`) |
| `2` | refused, nothing written; or no vault found; or concept files written but `.knott/schemas/` not deleted (see above) |
