---
type: command
title: knott view
synopsis: knott view [PATH] [-o FILE] [--no-open]
writes_files: true
concepts:
  - "[Ontology](../concepts/ontology.md)"
  - "[Schema](../concepts/schema.md)"
---
# knott view

Draws the vault's ontology as one static HTML page and opens it in the browser. `PATH` is any path inside the vault, default the current directory.

Each type is a box with its name and entity count. Each relation is an arrow: solid if required, dashed if optional. A relation to a type with no schema points to a dashed "ghost" box. Hover a type to highlight its neighbours. Click it to open a panel with its description, attributes, relations and the types that point to it.

Three layouts sit behind a toggle: **Layered** (default), **Force** and **Radial**. The page remembers the last one, and the URL hash (`#layered`, `#force`, `#radial`) selects one directly.

| Flag | Effect |
|---|---|
| `-o`, `--output FILE` | Write the page to `FILE`. Default: `knott-ontology-<vault>.html` in a private `knott-<uid>` folder in the temp directory, overwritten each run. |
| `--no-open` | Write the page without opening a browser. |

The page is self-contained: no server and no network. It prints `Wrote <path>` and exits `0`. If some schemas have errors, it still draws the types it could load, writes `N schema issues — run knott validate` to stderr, and exits `0`. If no browser opens, it writes `could not open a browser; open <path>` to stderr. A vault with no types, a `PATH` that doesn't exist, or an output file it cannot write (`error: cannot write <path>: …`) exits `2`. The default folder must be a real directory owned by you and closed to others; otherwise the command refuses to write there and exits `2`.
