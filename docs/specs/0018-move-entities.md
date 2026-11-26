---
type: spec
title: "0018: Move a file and rewrite the links to it"
status: implemented
created_on: 2026-11-26
released_in: "0.14.0"
realizes:
  - "[Move a file without breaking links](../intents/move-without-breaking-links.md)"
decisions:
  - "[0013](../decisions/0013-commands-may-make-mechanical-edits.md)"
  - "[0002](../decisions/0002-relative-paths-not-ids.md)"
  - "[0003](../decisions/0003-source-side-relations.md)"
  - "[0009](../decisions/0009-kid-identity.md)"
concepts:
  - "[Entity](../concepts/entity.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
  - "[File](../concepts/file.md)"
  - "[Kid](../concepts/kid.md)"
---
# 0018: Move a file and rewrite the links to it

## Summary

`knott mv SOURCE DEST` moves or renames one Markdown file and rewrites every link that the move would break: references to it in other entities' frontmatter, Markdown links to it in bodies, and the moved file's own relative links when its folder changes. Each link keeps its form and its label; only the path changes. `--dry-run` shows the changes without writing. It is the second command that edits user files, after `validate --fix`.

## Behaviour

### What can be moved

- `SOURCE` is a Markdown file in the vault that discovery sees: an entity or a plain note, outside `.knott/` and other hidden folders. It is a path relative to the current directory, or `kid:<uuid>`.
- A file whose frontmatter cannot be read is refused: its body cannot be told from its frontmatter.
- `DEST` is the new path, relative to the current directory. When `DEST` is an existing directory, the file keeps its name and goes into it.
- `DEST` must end in `.md`, be inside the vault, have no hidden folder in its path (`.knott/` included), and not exist. Missing parent folders are created. Nothing is ever overwritten.
- A `DEST` whose name contains `#` is refused: no reference can name such a file ([reference resolution](../concepts/reference-resolution.md)).
- Symbolic links are not followed ([0006](../decisions/0006-symlinks-and-containment.md)): a `SOURCE` that is a symbolic link is refused, and so is a `DEST` whose folder is reached through a symbolic link that leaves the vault.
- A rename that changes only letter case (`notes/Kid.md` to `notes/kid.md`) is allowed, also on a file system that ignores case.
- The file's content is otherwise unchanged. Its `kid` stays; a file without a `kid` does not get one.

### Links to the moved file

Every Markdown file in the vault is searched, and the bodies of relation, connector and loop files under `.knott/` (their guidance links to pages). Concept files are not: a concept's body is a template, and a link in it is relative to the entity that will copy it, not to the concept file. Files in other hidden folders are not searched.

**Frontmatter references.** A value is rewritten when it sits at a declared reference property of an entity, at any depth, and resolves by path to `SOURCE` ([reference resolution](../concepts/reference-resolution.md)).

- Matching is by the resolved file, not by text: `../specs/0006-x.md`, `./0006-x.md` and a Markdown link all match.
- A `kid:` reference is never changed. It still points at the entity.
- A reference that fails the target-type check is rewritten too; it points at the file.
- Not rewritten: keys no concept declares, the frontmatter of an entity whose type no concept defines, and the frontmatter of plain notes and of files under `.knott/`. Knott cannot tell a path from a string there.
- A `file` property that names `SOURCE` is rewritten the same way.

**Body links.** An inline link `[text](dest)` or image `![alt](dest)` is rewritten when `dest` is a relative path that resolves to `SOURCE`, with exact case.

- A `#fragment` after the path and a title after it (`(dest "title")`) are kept as written.
- `dest` may be wrapped in `<…>` and may be percent-encoded.
- Skipped: everything inside a fenced code block (` ``` ` or `~~~`) and inside an inline code span. Indented code blocks are not recognised: a link in one is rewritten. Neither is a fence indented by more than three spaces or inside a blockquote. A link inside an HTML comment is rewritten like any other.
- Not rewritten: wikilinks, reference-style definitions (`[id]: dest`), HTML attributes, autolinks and bare paths in text.

### The moved file's own links

When the file's folder changes, its own relative links would point elsewhere. They are rewritten so each still names the same file:

- every path value at its declared reference and `file` properties, at any depth (not `kid:` values, not URIs);
- every inline link and image in its body whose destination is a relative path, under the body rules above.

A link is rewritten only when it resolves to an existing file in the vault, with exact case; a folder is not a file. One that does not (already broken, leaving the vault, or not a path) is left as written and reported as `unchanged`. A link from the file to itself follows the move.

When only the name changes, the file's own links are not touched, except a link to itself.

### How a link is rewritten

The new destination is the shortest relative path from the linking file's folder to the target, with `/`, without a leading `./`. Only the destination changes:

| The old value | The new value |
|---|---|
| a plain path in frontmatter | the new path as is. `./` is put in front when the path would otherwise be read as something else: it starts with `[`, or its first segment contains `:` |
| any link whose new path has `:` in its first segment | `./` is put in front, in a Markdown link and in a body link too: `a:b.md` would read as a URI |
| a Markdown link with `<…>` | `<…>` is kept; `%`, `<` and `>` in the path are percent-encoded |
| a Markdown link without `<…>` | space, `%`, `(`, `)`, `<` and `>` in the path are percent-encoded |
| a body link, with or without `<…>` | as above, and `#` in the path is percent-encoded too: bare, it would start a fragment |

- The label, the title and the fragment are copied unchanged.
- A frontmatter value keeps its YAML quoting: inside `"…"`, `"` and `\` are escaped; inside `'…'`, `'` is doubled. A plain (unquoted) value stays plain when the new text is still a plain YAML string, and is written in double quotes otherwise.
- A value that cannot be edited in place is not guessed at: a block scalar (`|`, `>`), a scalar that spans several lines, or a value that reaches the property through a YAML alias or a merge key (`<<`). The move is refused and names the file and field.
- Every other byte of every file stays the same: line endings, a byte order mark, comments, key order, trailing spaces.

### Checks before writing

All edits are prepared in memory first.

1. Each edited file is parsed again. Its frontmatter must equal the old frontmatter with exactly the rewritten values replaced, and each rewritten link, resolved from the file's place after the move, must name the intended target.
2. If any file fails, nothing is written and the command names the file and field (exit 2).
3. A file whose frontmatter cannot be read has no known body, so it is not searched or edited. Every such file is reported as `skipped`, whether or not it links to `SOURCE`: knott cannot tell. A valid vault has none.
4. A Markdown file that is a symbolic link is not searched or edited either, and is reported as `skipped`: replacing it would replace the link, and its target may be outside the vault ([0006](../decisions/0006-symlinks-and-containment.md)).

### Writing

1. The moved file is written at `DEST` with its own links rewritten, keeping its permissions.
2. Each referring file is replaced atomically, in path order.
3. `SOURCE` is removed.

- An I/O error stops the command (exit 2) and names the files already written. Until step 3, `SOURCE` still exists, so a failed move leaves two copies and never zero.
- A case-only rename on a file system that ignores case renames the file in place, after step 2.
- An emptied source folder is left in place.
- Knott does not call Git. Git sees a rename when the result is staged.

### After the move

`mv` does not validate the vault. It makes one check on the moved entity, because the mistake is cheap to make and easy to miss: when its type declares `path` or `filename` and `DEST` does not fit, the move is still done and the `entity-misplaced` or `entity-invalid-name` issue is printed as a warning. Moving is also how such an issue is fixed, so it is not refused.

### `--dry-run`

Runs everything up to and including the checks, prints the same output with `would move` and `would update`, and writes nothing. The exit code is what the real run would give.

## CLI and API

```
knott mv SOURCE DEST [--dry-run] [--format text|json]
```

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

This is the vault as it was before specs 0016 to 0018 were added. `concepts/ontology.md` also names the file, inside an inline code span, so it is not touched.

- The first line is `moved`, the old path, `→` and the new path, vault-relative. After a blank line comes `updated N links in M files`, then one line per rewritten link: `path:line`, padded to the widest plus two spaces, then the property path, or `body`. Lines are ordered by path, then line. The moved file's own links are listed under its new path.
- With nothing to rewrite, the second block is `no links to update`.
- `unchanged` and `skipped` blocks follow when they have entries, each line ending with the reason:

  ```
  unchanged 1 link
    guides/tools/obsidian.md:14  body  `../img/missing.png` does not exist

  skipped 1 file
    notes/broken.md  cannot read the frontmatter: …
  ```
- A warning from the `path` or `filename` check is printed last, to stderr, in the format `validate` uses for an issue.
- `--format json`:

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

  `field` is `null` for a body link. For a frontmatter value, `old` and `new` are the whole value; for a body link, the destination only, with its fragment and without `<…>` or a title. `unchanged` entries have `path`, `line`, `field`, `value` and `reason`; `skipped` entries have `path` and `reason`. `issues` holds the `path` and `filename` warnings as `validate` issues.
- The vault is found from `SOURCE`, or from the current directory for `kid:`.
- Exit codes: `0` when the file was moved (or would be, with `--dry-run`), with or without warnings. `1` when the vault has the legacy layout. `2` for no vault, a `SOURCE` that doesn't exist, is outside the vault, is not a Markdown file knott sees or has unreadable frontmatter, a bad `DEST` (exists, not `.md`, outside the vault, in a hidden folder, the same file), a link that cannot be edited in place, a failed check, or an I/O error.

### Python API

- `Knott.move(source: str | Path, dest: str | Path, *, dry_run: bool = False) -> MoveResult`. Relative paths are resolved against the vault root; the CLI passes absolute paths. `source` may be `kid:<uuid>`.
- `MoveResult(from_, to, kid, dry_run, updated: list[UpdatedLink], unchanged: list[UnchangedLink], skipped: list[SkippedFile], issues: list[Issue])`. `from_` is `from` in JSON.
- Raises `PathNotFoundError`, `PathOutsideVaultError` or `KnottError` for the exit-2 cases. A new `MoveError(KnottError)` carries `written: list[str]` for an I/O error after the first write.

### The bundled skill and the guide

The rule "before renaming, deleting or replacing an entity, run `knott refs` and update those files" is split:

- **Rename or move** with `knott mv OLD NEW`. Never move an entity with `mv` or `git mv` and fix links by hand. Run `knott validate` afterwards and read the `unchanged` lines.
- **Delete or replace**: run `knott refs` first, as today.

## Edge cases

| Case | Result |
|---|---|
| `knott mv a.md b.md` and `b.md` exists | exit 2; nothing written |
| `knott mv specs/a.md archive/` and `archive/` is a folder | moved to `archive/a.md` |
| `knott mv specs/a.md archive/` and `archive` does not exist | exit 2: `DEST` does not end in `.md` |
| `knott mv specs/a.md archive/2026/a.md`, folders missing | created |
| `knott mv a.md .knott/a.md`, or into `.obsidian/` | exit 2 |
| `knott mv a.md b.md/a.md` and `b.md` is a file | exit 2, also with `--dry-run` |
| A symbolic link `linked.md` whose target links to `SOURCE` | not edited; in `skipped` |
| Writing `DEST` fails part-way | exit 2; the partial `DEST` is removed; `SOURCE` is untouched |
| `knott mv a.md a.md` | exit 2: the same file |
| `knott mv a.md "b#1.md"` | exit 2: a name with `#` cannot be referenced |
| `SOURCE` is a symbolic link | exit 2 |
| A link to `SOURCE` in a concept file's template | not rewritten |
| A reference written `kid:<uuid>` to the moved entity | unchanged, still resolves |
| An entity references the moved file twice, as a link and as a plain path | both rewritten, each in its form |
| The moved entity references itself | rewritten to the new name |
| A link in a fenced code block, or in `` `code` `` | not rewritten, not reported |
| A body link `[x](old.md#usage "Usage")` | `[x](new.md#usage "Usage")` |
| A body link whose destination only differs in case from `SOURCE` | not a link to it; unchanged |
| The new name has a space; the old link was `[x](old.md)` | `[x](new%20name.md)` |
| The new name has a space; the old link was `[x](<old name.md>)` | `[x](<new name.md>)` |
| A plain-path reference and the new path is `notes/a: b.md` | written `"notes/a: b.md"`, in double quotes |
| A plain-path reference and the new path is `notes/new name.md` | written plain: it still reads as the same string |
| A reference in a flow list, `[a.md, b.md]`, and the new name has a comma | that item is written in double quotes |
| A reference written as a block scalar (`ref: >` on its own line) | exit 2, naming the file and field; nothing written |
| A file with unreadable frontmatter, referring or not | not edited; in `skipped` |
| A referring entity whose type no concept defines | its body links are rewritten; its frontmatter is not |
| A path to `SOURCE` in an undeclared key | not rewritten and not reported |
| The moved file has `audio: ../audio/ep42.mp3` and changes folder | rewritten to reach the same mp3 |
| The moved file has `slides: s3://talks/ep42.pdf` | unchanged; not a path |
| The moved file has a reference to a file that does not exist | left as written; in `unchanged` |
| A plain note is moved | body links to it are rewritten; `kid` is `null` |
| `DEST` breaks the type's `filename` pattern | moved; `entity-invalid-name` warning; exit 0 |
| `--dry-run` | same output with `would move` / `would update`; no file changes |
| The disk fills while writing the third referring file | exit 2; the message lists the files written; `SOURCE` and `DEST` both exist |

## Out of scope

- Moving a folder or several files, and moving files that are not Markdown.
- Deleting an entity.
- Wikilinks, reference-style definitions, HTML attributes and paths in undeclared keys.
- Links from outside the vault. The repository `README.md` links into `docs/`; it is not in the vault, so it is not searched.
- Links inside concept templates.
- Overwriting (`--force`) and undo. Git is the undo.
- Staging the result in Git.
- Validating the vault after the move, beyond the `path` and `filename` warning.
- Creating entities or setting properties; [0013](../decisions/0013-commands-may-make-mechanical-edits.md) does not cover them.

## Compatibility

Additive: one new command and one new API method. No existing command changes. Knott reads bodies in two places, `show --body` ([0016](0016-list-and-show-entities.md)) to print one and `mv` to rewrite link destinations; it still never checks them. The pages that say knott does not read the body (the entity concept page, the bundled skill) are reworded to "does not check" in the same change. Version 0.14.0, together with [0016](0016-list-and-show-entities.md) and [0017](0017-types-for-one-type.md).
