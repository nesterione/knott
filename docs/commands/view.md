---
type: command
title: knott view
synopsis: knott view [PATH] [-o FILE] [--no-open]
writes_files: true
concepts:
  - "[Ontology](../concepts/ontology.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Loop](../concepts/loop.md)"
---
# knott view

Draws the vault's ontology as one static HTML page and opens it in the browser. `PATH` is any path inside the vault, default the current directory.

Each type is a box with its name and entity count. Each reference is an arrow labelled with its path (`derived_from`, `speakers[].person`), or with its [relation](../concepts/relation.md) when it names one (`about`), one per target type: solid if required, dashed if optional. A nested reference counts as required only when every step on its path is required. A target that no concept defines gets no arrow. Hover a type to highlight its neighbours. Click it to open a panel with:

- its parent, its subtypes and whether it is abstract, when it is part of a [hierarchy](../concepts/schema.md#inheritance); inherited properties, references and loops are marked `from <type>`
- the folders its entities are stored in, when the concept declares `path`
- the pattern its file names follow and the parts of it, when the concept declares `filename`
- its description, properties (with the relation a reference names, unknown targets marked `(unknown)`, the extensions a [file](../concepts/file.md) accepts, and the options of an enum) and body template
- **References out**: each reference's path, with its relation in parentheses
- **Referenced by**: every reference property, in any type, that can point at this one, grouped and labelled as [`knott refs`](refs.md) groups them (`discussed_in`, `related`, `← guide.concepts[]`). Each row is `<type>.<path>`.

An [open reference](../concepts/relation.md#open-references) (`target: any`) has no arrow. The type that declares it carries a `→ any` mark, with `×N` for several, and **Open references (N)** in the header highlights every such type. Every type's panel lists the vault's open references under "from anywhere".

With [inheritance](../concepts/schema.md#inheritance), a reference is drawn once, at the type that declares it, and "is a" is its own edge: thin, with a hollow triangle at the parent. An abstract type has a dashed border and its name in italics. A type with subtypes carries a `▾ N` mark; click it to fold the subtypes into the parent, and the edges of the hidden types are drawn at the parent. **Fold subtypes** in the header does it for every family. Hovering a type also highlights the references it inherits.

A **Relations (N defined · M inline)** button in the header lists every link in the vault, in two sections:

- **Defined**: each [relation file](../concepts/relation.md#relation-definitions) with its keys and description, its guidance folded under "When to use it", and the properties that name it.
- **Inline**: every reference that names no relation file, as `<type>.<path>`, grouped by what it points at, largest group first. Several inline relations with one target are the ones to consider for a shared relation file.

The button is hidden only when the vault has neither.

A **Loops (N)** button opens a board for the vault's [loops](../concepts/loop.md), one loop at a time, over the diagram. A dropdown switches loops, and the URL hash `#loop=<name>` opens one directly.

- **Columns** are the stages on the path, in order, then the side exits, dimmed, then `no stage` when it has entities. Click a column header to see what the stage needs and its guidance.
- **Cards** are entities: the title (the `title` property when the type has one, else the file name), the path, and what the next stage still needs, or `ready`.
- **A red card** is at a stage whose needs it doesn't meet; `knott validate` reports the same as [`loop-stage-unmet`](../issues/loop-stage-unmet.md).

A type's panel also lists the loops that follow it, with entity counts per stage. The button is hidden when the vault has no loops. With loops, the page contains the title, path and `kid` of each entity whose type has a loop; keep that in mind before sharing the file. Cards are not links: the page is static and usually sits in a temp folder.

Three layouts sit behind a toggle: **Layered** (default), **Force** and **Radial**. The page remembers the last one, and the URL hash (`#layered`, `#force`, `#radial`) selects one directly.

| Flag | Effect |
|---|---|
| `-o`, `--output FILE` | Write the page to `FILE`. Default: `knott-ontology-<vault>.html` in a private `knott-<uid>` folder in the temp directory, overwritten each run. |
| `--no-open` | Write the page without opening a browser. |

The page is self-contained: no server and no network. It prints `Wrote <path>` and exits `0`. If some schemas have errors, it still draws the types it could load, writes `N schema issues — run knott validate` to stderr, and exits `0`. If no browser opens, it writes `could not open a browser; open <path>` to stderr. A vault that still has `.knott/schemas/` gets the [`schema-legacy-layout`](../issues/schema-legacy-layout.md) issue on stderr, no page, and exit `1`; run [`knott migrate`](migrate.md) first. A vault with no types, a `PATH` that doesn't exist, or an output file it cannot write (`error: cannot write <path>: …`) exits `2`. The default folder must be a real directory owned by you and closed to others; otherwise the command refuses to write there and exits `2`.
