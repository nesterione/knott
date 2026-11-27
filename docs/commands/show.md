---
type: command
title: knott show
synopsis: knott show PATH [--body] [--format text|json]
writes_files: false
concepts:
  - "[Entity](../concepts/entity.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
---
# knott show

Prints one entity as data: its properties, each outgoing reference resolved to the target's path and type, and who references it. The body is left out unless you ask for it, so reading an entity's connections does not cost its whole text.

`PATH` is an entity file, relative to the current directory, or `kid:<uuid>`, as for [`knott refs`](refs.md).

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

- **The first line** is the path and the type, then `kid:<uuid>` when the entity has a [kid](../concepts/kid.md).
- **`properties`** lists the frontmatter keys other than `type` and `kid`, in file order, with values printed as [`knott list`](list.md#output) prints them. Keys no concept declares are included. A property declared as a reference, or a list of references, is not repeated here: it is under `references`.
- **`references`** lists every value of a declared reference property, at any depth: the field (`realizes[0]`, `speakers[1].person`), the target's path and type, and the [relation](../concepts/relation.md) in parentheses when the property names one.
- **`referenced by`** is what [`knott refs`](refs.md) prints for the entity.
- A section with nothing in it is left out.

`show` does not validate. A reference with a problem is still listed, with the issue code `knott validate` reports for it:

```
references
  about         c/git.md         tool
  affects[0]    t/one.md         task                        relation-target-type-mismatch
  steps[0].who  c/git.md         tool
  steps[1].who  ../c/missing.md  relation-target-not-found
  roles.lead    c/plain.md       relation-target-not-entity
```

A value that resolves to no file is shown as written, with the code where the type would be. A file that is not an entity shows its path and the code. A target of the wrong type shows its path and type, then the code. A property with the wrong cardinality (one value where a list is declared, or the reverse) is one row for the whole property, with `relation-invalid-value`.

`--body` adds a `body` section at the end with the body verbatim, not indented. An entity with a blank body has no such section.

`--format json` prints the same data. `properties` holds every key, references included, with values as written; `referenced_by` is the `groups` list of `knott refs --format json`; `body` is there only with `--body`, and is `null` for a blank body:

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

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | the vault still has `.knott/schemas/`: the [`schema-legacy-layout`](../issues/schema-legacy-layout.md) issue goes to stderr |
| `2` | no vault, `PATH` doesn't exist or is outside the vault, `PATH` isn't an entity (a file outside the [included folders](../concepts/vault.md#included-folders) is never one), or a `kid:` is malformed or matches no entity or several |
