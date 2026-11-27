---
type: command
title: knott mv
synopsis: knott mv SOURCE DEST [--dry-run] [--format text|json]
writes_files: true
concepts:
  - "[Entity](../concepts/entity.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
  - "[File](../concepts/file.md)"
  - "[Kid](../concepts/kid.md)"
---
# knott mv

Moves or renames one Markdown file and rewrites every link the move would break. References are paths relative to the file that holds them, so a plain `mv` or `git mv` breaks each link to the file, and, when its folder changes, the file's own links too. `knott mv` fixes all of them in one step; each link keeps its form and its label, and only the path changes.

```
$ knott mv specs/0006-relation-definitions.md specs/0006-relations.md
moved specs/0006-relation-definitions.md → specs/0006-relations.md

updated 7 links in 6 files
  README.md:72                             body
  concepts/relation.md:123                 body
  intents/relation-definitions.md:26       body
  specs/0007-view-inline-relations.md:13   amends[0]
  specs/0013-concept-inheritance.md:20     amends[1]
  specs/0013-concept-inheritance.md:111    body
  specs/0014-open-reference-targets.md:19  amends[1]
```

This is the docs vault as it was before specs 0016 to 0019 were added; today the same command updates nine links. `concepts/ontology.md` also names the file, inside an inline code span, so it is not touched.

- `SOURCE` is a Markdown file in the vault, an entity or a plain note: a path relative to the current directory, or `kid:<uuid>`.
- `DEST` is the new path, relative to the current directory. If it is an existing folder, the file keeps its name and goes into it. Missing folders are created.
- `--dry-run` prints the same report with `would move` and `would update`, and writes nothing.

## What is rewritten

**Links to the moved file**, in every Markdown file of the vault and in the guidance of relation, connector and loop files:

- **Frontmatter**: a value of a declared [reference](../concepts/relation.md) or [file](../concepts/file.md) property, at any depth, that names the file by path. A plain path and a Markdown link both match, whatever relative path they use. A `kid:` reference is left alone: it still points at the entity.
- **Bodies**: an inline link `[text](dest)` or image `![alt](dest)` whose destination is a relative path to the file. A `#fragment` and a title are kept. The destination may be wrapped in `<…>` or percent-encoded.

**The moved file's own links**, when its folder changes: the path values of its declared reference and file properties, and the relative links and images in its body. Each is rewritten to reach the same file from the new place. A link that names no existing file in the vault is left as written and listed under `unchanged`.

Not rewritten:

- links inside fenced code blocks and inline code spans
- wikilinks, reference-style definitions (`[id]: dest`), HTML attributes, autolinks and bare paths in text
- keys no concept declares, and the frontmatter of plain notes, of entities whose type no concept defines, and of files under `.knott/`: knott cannot tell a path from a string there
- concept files: a link in a template is relative to the entity that will copy it
- files in hidden folders other than `.knott/`, files outside the [included folders](../concepts/vault.md#included-folders), and anything outside the vault

A link in an indented code block is rewritten, since indented code is not recognised; so is one in a fence indented by more than three spaces or inside a blockquote. A link in an HTML comment is rewritten like any other.

## How a link is rewritten

The new destination is the shortest relative path from the linking file's folder to the target. Everything else about the link stays:

| The old value | The new value |
|---|---|
| a plain path in frontmatter | the new path. A value that no longer reads as a plain YAML string is put in double quotes |
| a quoted value in frontmatter | the same quotes, with the path escaped for them |
| a Markdown link with `<…>` | `<…>` is kept |
| a Markdown link without `<…>` | spaces, `%`, `(`, `)`, `<` and `>` in the path are percent-encoded |

A path whose first segment contains `:` gets `./` in front, so it is not read as a URI. Every other byte of every file stays the same: line endings, comments, key order, trailing spaces.

A value that cannot be edited in place stops the move before anything is written: a block scalar (`|`, `>`), a value that spans several lines, or one that reaches the property through a YAML alias or merge key. The message names the file and the field; rewrite that value on one line and run the move again.

## Safety

- **Nothing is overwritten.** `DEST` must not exist.
- **Everything is checked before anything is written.** All edits are prepared in memory. Each edited file is parsed again: its frontmatter must equal the old one with only the rewritten values changed, and each rewritten link must name the intended file from the file's new place. If one file fails, nothing is written.
- **A failed write never loses the file.** The file is written at `DEST` first, then the referring files, and `SOURCE` is removed last. If writing stops, the message lists the files already written, and both copies exist.
- **Knott does not call Git.** Git sees a rename once the result is staged. Git is also the undo.

`mv` does not validate the vault. It makes one check on the moved entity: when its type declares [`path`](../concepts/schema.md#where-entities-live) or [`filename`](../concepts/schema.md#file-names) and `DEST` does not fit, the move is still done and [`entity-misplaced`](../issues/entity-misplaced.md) or [`entity-invalid-name`](../issues/entity-invalid-name.md) is printed as a warning on stderr. Run `knott validate` afterwards.

## Output

The first line is the old path, `→` and the new one. Then `updated N links in M files` with one line per rewritten link: `path:line`, then the property path, or `body`. The moved file's own links are listed under its new path. With nothing to rewrite, the block is `no links to update`.

Two more blocks follow when they have entries:

```
unchanged 1 link
  guides/tools/obsidian.md:14  body  `../img/missing.png` does not exist

skipped 1 file
  notes/broken.md  cannot read the frontmatter: …
```

- **`unchanged`**: links of the moved file that were left as written.
- **`skipped`**: every file whose frontmatter cannot be read (its body cannot be told from its frontmatter) and every Markdown file that is a symbolic link (knott does not edit through one). They are not searched; check them by hand.

`--format json` prints the same data:

```json
{
  "from": "specs/0006-relation-definitions.md",
  "to": "specs/0006-relations.md",
  "kid": null,
  "dry_run": false,
  "updated": [
    {"path": "specs/0007-view-inline-relations.md", "line": 13, "field": "amends[0]",
     "old": "[0006](0006-relation-definitions.md)", "new": "[0006](0006-relations.md)"},
    {"path": "README.md", "line": 72, "field": null,
     "old": "specs/0006-relation-definitions.md", "new": "specs/0006-relations.md"}
  ],
  "unchanged": [],
  "skipped": [],
  "issues": []
}
```

`field` is `null` for a body link. For a frontmatter value, `old` and `new` are the whole value; for a body link, the destination. `issues` holds the `path` and `filename` warnings.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | the file was moved (or would be, with `--dry-run`), with or without warnings |
| `1` | the vault still has `.knott/schemas/`: the [`schema-legacy-layout`](../issues/schema-legacy-layout.md) issue goes to stderr |
| `2` | no vault; `SOURCE` doesn't exist, is outside the vault, is a symbolic link, is not a Markdown file knott sees (outside the [included folders](../concepts/vault.md#included-folders) too), or has unreadable frontmatter; `DEST` exists, does not end in `.md`, is outside the vault or the included folders, is in a hidden folder, has a `#` in its path, or is the same file; a link that cannot be edited in place; a failed check; an I/O error |

Out of scope: moving a folder or several files, moving files that are not Markdown, and deleting an entity. Before deleting or replacing an entity, run [`knott refs`](refs.md).
