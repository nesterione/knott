---
type: command
title: knott view
synopsis: knott view [PATH] [-o FILE] [--no-open]
writes_files: true
concepts:
  - "[Ontology](../concepts/ontology.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Relation](../concepts/relation.md)"
---
# knott view

Draws the vault's ontology as one static HTML page and opens it in the browser. `PATH` is any path inside the vault, default the current directory.

Each type is a box with its name and entity count. Each reference is an arrow labelled with its path (`derived_from`, `speakers[].person`), or with its [relation](../concepts/relation.md) when it names one (`about`), one per target type: solid if required, dashed if optional. A nested reference counts as required only when every step on its path is required. A target that no concept defines gets no arrow. Hover a type to highlight its neighbours. Click it to open a panel with:

- its description, properties (with the relation a reference names, and unknown targets marked `(unknown)`) and body template
- **References out**: each reference's path, with its relation in parentheses
- **Referenced by**: every reference property, in any type, that can point at this one, grouped and labelled as [`knott refs`](refs.md) groups them (`discussed_in`, `related`, `← guide.concepts[]`). Each row is `<type>.<path>`.

A **Relations (N defined · M inline)** button in the header lists every link in the vault, in two sections:

- **Defined**: each [relation file](../concepts/relation.md#relation-definitions) with its keys and description, its guidance folded under "When to use it", and the properties that name it.
- **Inline**: every reference that names no relation file, as `<type>.<path>`, grouped by what it points at, largest group first. Several inline relations with one target are the ones to consider for a shared relation file.

The button is hidden only when the vault has neither.

Three layouts sit behind a toggle: **Layered** (default), **Force** and **Radial**. The page remembers the last one, and the URL hash (`#layered`, `#force`, `#radial`) selects one directly.

| Flag | Effect |
|---|---|
| `-o`, `--output FILE` | Write the page to `FILE`. Default: `knott-ontology-<vault>.html` in a private `knott-<uid>` folder in the temp directory, overwritten each run. |
| `--no-open` | Write the page without opening a browser. |

The page is self-contained: no server and no network. It prints `Wrote <path>` and exits `0`. If some schemas have errors, it still draws the types it could load, writes `N schema issues — run knott validate` to stderr, and exits `0`. If no browser opens, it writes `could not open a browser; open <path>` to stderr. A vault that still has `.knott/schemas/` gets the [`schema-legacy-layout`](../issues/schema-legacy-layout.md) issue on stderr, no page, and exit `1`; run [`knott migrate`](migrate.md) first. A vault with no types, a `PATH` that doesn't exist, or an output file it cannot write (`error: cannot write <path>: …`) exits `2`. The default folder must be a real directory owned by you and closed to others; otherwise the command refuses to write there and exits `2`.
