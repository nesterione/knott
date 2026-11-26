---
type: spec
title: "0015: Type tree"
status: implemented
created_on: 2026-11-26
released_in: "0.13.0"
realizes:
  - "[Type tree](../intents/type-tree.md)"
concepts:
  - "[Ontology](../concepts/ontology.md)"
  - "[Schema](../concepts/schema.md)"
amends:
  - "[0001](0001-ontology-viewer.md)"
  - "[0013](0013-concept-inheritance.md)"
---
# 0015: Type tree

## Summary

`knott types --tree` prints the vault's types as a tree: subtypes indented under their parent, each with its entity count and folder. With `--verbose` every type also gets its description and the properties it adds. `knott view` gains an **Outline** panel with the same tree; a click on a row selects the type in the diagram. Nothing breaks: `knott types` and `knott types --verbose` print what they print today.

## Behaviour

### The tree

- **Roots** are the types with no parent, sorted by name. A concept whose parent is unknown or part of a cycle loads as a root ([0013](0013-concept-inheritance.md)) and is listed as one.
- **Children** are a type's direct subtypes, sorted by name, at any depth.
- **Every loaded type appears once.** A type whose concept file failed to load is absent, as in `knott types`.

### A row

```
<prefix><name>[ (abstract)]  <count>  <path>
```

- **`<prefix>`** is empty for a root. Otherwise it is one segment per ancestor below the root, `│  ` when that ancestor has a later sibling and three spaces when it has none, then `├─ ` for the type itself, or `└─ ` when it is the last child.
- **` (abstract)`** follows the name of an abstract type.
- **`<count>`** is the number of entities whose frontmatter `type` is exactly this type, as `OntologyType.count`. Subtypes are not added in. An abstract type has no count: the column is left blank.
- **`<path>`** is the type's `path` patterns, its own or inherited, as the `path:` line of `knott types --verbose` prints them, joined with ` | `. It is left out when the type has none.
- **Alignment.** `<prefix><name>[ (abstract)]` is padded to the widest such label in the tree; the count is right-aligned to the widest count. Columns are separated by two spaces. A line never ends in spaces.

```
$ knott types --tree
concept            12  concepts
note                3
record (abstract)
├─ decision        12  decisions
└─ spec            14  specs
```

### `--tree --verbose`

Each row is followed by up to two detail lines:

1. **The description**, with every run of whitespace replaced by one space, on one line. Left out when the concept has none.
2. **`adds: `** and the top-level properties the type declares itself, in schema order, joined with `, `. A required property ends with `*`. Inherited properties are not listed. Left out when the type declares none.

A detail line starts with the row's ancestor segments, then `│  ` when the row is not the last child (three spaces when it is; nothing for a root), then `│  ` when the type has subtypes (three spaces when it has none), then the text.

```
$ knott types --tree --verbose
concept            12  concepts
   A core idea in Knott's model. Read concepts first to understand what the other documents refer to.
   adds: title*, summary*, spec_section, related
note                3
record (abstract)
│  Anything with a title and a date.
│  adds: title*, created_on*
├─ decision        12  decisions
│     Why a choice was made.
│     adds: status*, supersedes
└─ spec            14  specs
      The exact behaviour one change adds or alters.
      adds: status*, realizes, decisions, concepts
```

The `relations:`, `connectors:` and `loops:` sections are not printed with `--tree`. Nested shapes, targets, options, templates and file-name patterns stay in `knott types --verbose`.

## CLI and API

### `knott types`

| Flag | Effect |
|---|---|
| `--tree`, `-t` | Print the types as a tree with entity counts and folders. |
| `--tree --verbose` | Add each type's description and the properties it adds. |

- `--tree` reads every Markdown file in the vault to count entities, as `knott view` does. Plain `knott types` still reads concept files only.
- Exit codes and stderr are those of `knott types`: schema issues go to stderr and the exit code is `1`, with the tree of the types that loaded on stdout. A vault with no types prints nothing. A vault that still has `.knott/schemas/` prints no tree and reports `schema-legacy-layout`.
- Files with invalid frontmatter, and entities whose type no concept defines, are not counted and not reported here.

### `knott view`

- **A header button, `Outline`**, before `Relations`. It opens a panel on the left of the diagram; the diagram keeps the remaining width. Whether it is open is remembered in its own `localStorage` entry, for every vault; no URL hash sets it. It is always shown: a vault with types has an outline.
- **The panel** lists the same tree in the same order, one row per type: indentation by depth, the name, and the entity count at the right edge. An abstract type's name is in italics and it has no count. A row's tooltip is the type's description.
- **The outline is always fully expanded.** Folding subtypes in the diagram does not change it.
- **Hovering a row** highlights the type in the diagram exactly as hovering its box does. Hovering a box marks its row. For a type hidden because an ancestor is folded, the folded ancestor's box is highlighted instead.
- **Clicking a row** selects the type: its details panel opens, as on a click on its box, and the row stays marked while the panel is open. If the type is hidden because an ancestor is folded, those ancestors are unfolded first.
- **A loop board** covers the outline as it covers the diagram. The Relations list and a type's details open on the right as today, with the outline still on the left.

**Embedded data.** None added: the outline is built from each type's `type`, `extends`, `abstract`, `count` and `description`, which the page already carries.

### Python API

No change. `Knott.ontology()` already returns everything the tree shows (`extends`, `subtypes`, `abstract`, `count`, `entity_paths`, `description`, and `inherited_from` on each property).

### Agent skill and guide

To add to the bundled skill when this is implemented:

- Run `knott types --tree` first in an unfamiliar vault: it shows which types exist, which are kinds of which, how many entities each has and the folder they live in. `--tree --verbose` adds what each type is for.
- A type marked `(abstract)` cannot be an entity's `type`; pick one of the types under it.
- The tree is an overview. Before writing an entity, still read the type in `knott types --verbose`: the tree shows property names, not their shapes, targets or options.

## Edge cases

| Case | Result |
|---|---|
| No concept uses `extends` | Every type is a root: a sorted list with counts and folders, no tree characters |
| A type with entities and subtypes | Its count is its own entities only |
| An abstract type with a `path` | The count column is blank and the path is shown |
| A subtype that inherits its `path` | The inherited path is shown, with no `(from …)` mark |
| A type with no entities | Count `0` |
| Every type is abstract | No count column: `record (abstract)  records` |
| An abstract type that entities name as their `type` | The count column stays blank; `knott validate` reports each as `entity-abstract-type` |
| Outline: hover a type hidden by a folded ancestor | The folded ancestor's box is highlighted |
| `path` with several patterns | `episodes/* \| archive/**` |
| `extends` names an unknown type, or is part of a cycle | The type is a root; the issue goes to stderr and the exit code is `1` |
| A description written over several lines | One line in `--tree --verbose` |
| A type that declares no properties of its own | No `adds:` line |
| A type with neither description nor own properties | The row only, also with `--verbose` |
| `--verbose` given before or after `--tree` | Same output |
| Outline: click a type hidden by a folded ancestor | The ancestors unfold and the type is selected |

## Out of scope

- Listing entities under their type. That would be a separate command (`knott tree`), and in the view it would put every entity's title and path into the page.
- A count that adds subtypes in.
- JSON output for `knott types`.
- Reference targets, loops or relations in the tree.
- A tree layout for the diagram itself: the outline navigates, the diagram shows the links.

## Compatibility

Additive. `knott types` and `knott types --verbose` are unchanged, the Python API and the view's embedded data are unchanged. Version 0.13.0.
