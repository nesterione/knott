---
type: intent
title: Move a file without breaking links
status: open
raised_on: 2026-11-26
concepts:
  - "[Entity](../concepts/entity.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
---
# Move a file without breaking links

## Need

References are paths relative to the file that holds them ([0002](../decisions/0002-relative-paths-not-ids.md)). Renaming or moving a file breaks every reference to it, and moving it to another folder also breaks its own references. Today an agent runs `knott refs`, then edits each referring file by hand, working out a new relative path for each folder. It is the most error-prone thing an agent does in a vault:

- one missed file leaves a broken reference;
- `knott refs` lists declared references only, so links in bodies and in plain notes are found with `grep`, or not at all;
- `knott validate` catches a broken reference, but never a broken link in a body.

Obsidian fixes links on rename, but only when the rename happens inside Obsidian. An agent works on the files.

## Example

In this folder, `specs/0006-relation-definitions.md` is referenced from the frontmatter of three specs and linked from four bodies, among them `README.md`, which is a plain note. Renaming it should be one command that leaves `knott validate` passing and every one of those links working. Moving `guides/obsidian.md` into a new `guides/tools/` folder should also fix the guide's own links to `../concepts/…`.

## Open questions

Moving one Markdown file is answered by [spec 0018](../specs/0018-move-entities.md), under [decision 0013](../decisions/0013-commands-may-make-mechanical-edits.md). Left for later specs:

- Moving a folder, or several files in one command.
- Moving a file that is not Markdown (an mp3 or an image that `file` properties and body images point at).
- Deleting an entity: refusing while something references it, or listing what would break.
- Links knott does not rewrite: wikilinks, reference-style link definitions, HTML `href`, and paths in undeclared frontmatter keys.
