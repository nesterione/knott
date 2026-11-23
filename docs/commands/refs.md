---
type: command
title: knott refs
synopsis: knott refs PATH [--format text|json]
writes_files: false
concepts:
  - "[Relation](../concepts/relation.md)"
  - "[Entity](../concepts/entity.md)"
---
# knott refs

Lists every reference in the vault that points at one entity, grouped by what the link means. References are stored on the source side only, so this is how you read a link from the target side. Run it before renaming, deleting or replacing an entity.

`PATH` is an entity file, relative to the current directory, or `kid:<uuid>`. The vault is found from `PATH`, or from the current directory for `kid:`.

## Output

```
$ knott refs concepts/kid.md
concepts/kid.md  concept

discussed_in
  decisions/0009-kid-identity.md  decision    affects[0]
  issues/kid-duplicate.md         issue_code  about
  issues/kid-invalid.md           issue_code  about
  issues/kid-missing.md           issue_code  about

related
  concepts/entity.md                concept  related[0]  →
  concepts/reference-resolution.md  concept  related[1]  →
  concepts/schema.md                concept  related[2]  →

← spec.concepts[]
  specs/0004-kid-identity.md  spec  concepts[0]
```

The first line is the entity and its type. Each reference line is the source's path, its type, and the field that holds the reference. The group label depends on the referring property:

| The property | Label | Example |
|---|---|---|
| names a [relation](../concepts/relation.md) with an `inverse` | the inverse | `discussed_in`, for `about` |
| names a symmetric relation | the relation's name | `related` |
| names a relation with neither | `← <relation>` | `← about` |
| names no relation | `← <type>.<path>` | `← spec.concepts[]` |

- **Properties that name one relation share a group**, whatever their concept or key: `decision.affects` and `issue_code.about` both appear under `discussed_in`.
- **Symmetric groups show both sides.** They include the entity's own references too, with a direction at the end: `←` only the other side stores the link, `→` only this entity does, `⇄` both do.
- **Wrong-type references are listed**, because they still point at the entity. `knott validate` reports the mismatch.
- **Groups are ordered** by label, with `← <type>.<path>` groups last. References within a group are ordered by path.

An entity nobody references prints its header line, a blank line and `no references`.

`--format json` prints the same data (shortened here):

```json
{
  "entity": {"path": "concepts/kid.md", "type": "concept", "kid": null},
  "groups": [
    {"label": "discussed_in", "kind": "inverse", "relation": "about",
     "references": [{"path": "decisions/0009-kid-identity.md", "type": "decision",
                     "kid": null, "field": "affects[0]", "line": 7, "direction": "in"}, …]},
    …
  ]
}
```

`kind` is `inverse`, `symmetric`, `relation` or `property`. `relation` is `null` for `property` groups. `direction` is `in`, `out` or `both`, and always `in` outside symmetric groups.

`refs` does not validate. Schema issues don't stop it; it uses the concept and relation files that loaded.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success, including an entity with no references |
| `1` | the vault still has `.knott/schemas/`: the [`schema-legacy-layout`](../issues/schema-legacy-layout.md) issue goes to stderr |
| `2` | no vault, `PATH` doesn't exist or is outside the vault, `PATH` isn't an entity (a concept or relation file, a folder, a note without `type`, unreadable frontmatter), or a `kid:` is malformed or matches no entity or several |

```
$ knott refs .knott/concepts/concept.md
error: not a Knott entity: .knott/concepts/concept.md; expected a Markdown file in the vault (outside `.knott/` and hidden folders) whose YAML frontmatter has a `type` key
```
