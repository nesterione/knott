---
type: spec
title: "0001: Add `knott view` to draw the ontology as an HTML page"
status: implemented
created_on: 2026-10-07
released_in: "0.3.0"
concepts:
  - "[Ontology](../concepts/ontology.md)"
  - "[Schema](../concepts/schema.md)"
---
# 0001: Add `knott view` to draw the ontology as an HTML page

## Summary

`knott view` draws the vault's ontology (its types and the typed relations between them) as one self-contained HTML page and opens it in the browser. Before this, the only view of the ontology was `knott types --verbose`, which showed no relations, and a hand-drawn diagram that went stale. The same data is available from Python as `Knott.ontology()`. Nothing breaks.

## Behaviour

### Ontology model

`Knott.ontology()` returns a plain, JSON-serialisable model:

```python
class OntologyAttribute(_Frozen): name: str; type: str; required: bool; description: str | None
class OntologyRelation(_Frozen):  name: str; target: str; required: bool; description: str | None
                                  target_known: bool          # False: no schema defines the target
class OntologyType(_Frozen):      type: str; description: str | None; path: str; count: int
                                  attributes: list[OntologyAttribute]; relations: list[OntologyRelation]
class Ontology(_Frozen):          vault: str; types: list[OntologyType]; schema_issues: int
```

- `vault` is the vault root's directory name.
- Types are sorted by name. Attributes and relations keep their schema order.
- `path` is the vault-relative path of the schema file.
- `count` is the number of Markdown files whose frontmatter `type` equals the type name. Files with invalid frontmatter are skipped. Relations are not resolved.
- `schema_issues` is the number of schema problems. Types that loaded are still listed.
- A relation whose target type no schema defines is kept, listed after the type's other relations with `target_known: false`. Schema loading still reports `schema-unknown-target` for it, and entity validation still ignores it.
- "Referenced by" and layouts are not stored; the page computes them.

### The page

- One template with inline CSS and JS. No CDN, no network, no server. The model's JSON is injected into a `<script>`. `</` is written as `<\/` and `<!--` as `<\u0021--`, so no schema text can close the script or switch the HTML parser's script state. Lone surrogates are written as `\uXXXX`, so the page always encodes as UTF-8.
- The header shows `<vault> · N types · M relations · K entities`. When `schema_issues > 0`, a muted note under it says `N schema issues — run knott validate`.
- Each type is a pill with its name and entity count. Each relation is an edge: solid if required, dashed if optional. A self-relation is a loop on the pill corner farthest from the node's other edges; several self-relations on one type take different corners. Parallel relations between two types fan out.
- A relation with `target_known: false` points to a ghost node: dashed outline, no count. Its panel says "undefined type — no schema".
- Hovering a type highlights its neighbours. Clicking opens a side panel with the description, attributes, outgoing relations and "Referenced by". Opening or closing the panel refits the view.
- Type names are ordinary keys: names such as `constructor` or `toString` work.

### Layouts

Three layouts sit behind a toggle, with animated transitions:

- **Layered** (default). Edge labels sit near the source end (t ≈ 0.3). Types with no relations to other types go in a trailing column, and tall columns wrap.
- **Force.** Resizing keeps the current positions.
- **Radial.** The hub is the defined (non-ghost) type with the highest in-degree, ignoring self-loops. A tie goes to the first type by name.

The page fits the layout to the window on load and on (debounced) resize. The mode is saved in `localStorage` and mirrored in `location.hash` (`#layered`, `#force`, `#radial`). On load the hash wins over storage, and storage wins over the default. The hash is read on load only.

## CLI and API

```
knott view [PATH] [-o/--output FILE] [--no-open]
```

| Flag | Effect |
|---|---|
| `PATH` | Any path inside the vault, default `.`. |
| `-o`, `--output FILE` | Write the page to `FILE`. |
| `--no-open` | Write the page without opening a browser. |

- Without `-o`, the page goes to `<tempdir>/knott-<uid>/knott-ontology-<vault>.html` and is overwritten on each run. The `knott-<uid>` folder is created with mode `0700`. If it is a symlink, not a folder, owned by another user or open to others, the command refuses to write there.
- On success it prints `Wrote <path>` and exits `0`, also when some schemas have errors. Then stderr also gets `N schema issues — run knott validate`.
- If the browser can't be opened, stderr gets `could not open a browser; open <path>`. The exit code stays `0`.
- Exit `2` with `error: …`:
  - no types: `error: no types to show (add schemas to .knott/schemas/)`
  - the output can't be written, including a refused temp folder: `error: cannot write <path>: …`
  - `PATH` doesn't exist or isn't in a vault.

Python: `Knott.ontology() -> Ontology`. `Ontology`, `OntologyType`, `OntologyAttribute` and `OntologyRelation` are exported from `knott`. `knott.view.render_ontology(ontology) -> str` returns the page; a template without the data placeholder raises `RuntimeError`.

## Edge cases

- A schema with errors: the page still shows every type that loaded, plus the issue note. Exit `0`.
- A vault with schemas but no entities: all counts are `0`; the page is still drawn.
- A description containing `</script><script>alert(1)`: shown as text, never run.
- A relation to an undefined type: drawn to a ghost node; the ghost is never the radial hub.
- An empty vault (no schemas): exit `2`, no page.
- A shared `/tmp` where another user created `knott-<uid>`: refused, exit `2`.

## Out of scope

Search, zoom and pan, entity listing, saved drag positions, PNG export, per-type colours, and a live `--watch` mode. A watch mode could be added later without changing the page.

## Compatibility

Additive. `validate` and `types` output is unchanged. The new public models and `Knott.ontology()` are new API. Released as 0.3.0.
