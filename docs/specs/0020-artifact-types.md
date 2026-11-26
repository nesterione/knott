---
type: spec
title: "0020: Artifact types"
status: draft
created_on: 2026-11-26
realizes:
  - "[Artifacts](../intents/artifacts.md)"
decisions:
  - "[0014](../decisions/0014-artifact-types-are-places-not-entities.md)"
  - "[0012](../decisions/0012-files-are-property-values.md)"
  - "[0006](../decisions/0006-symlinks-and-containment.md)"
concepts:
  - "[File](../concepts/file.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Ontology](../concepts/ontology.md)"
  - "[Vault](../concepts/vault.md)"
amends:
  - "[0008](0008-file-properties.md)"
  - "[0001](0001-ontology-viewer.md)"
  - "[0015](0015-type-tree.md)"
---
# 0020: Artifact types

## Summary

A vault can describe a kind of file once, as an **artifact type** in `.knott/artifacts/`: where such files are stored, which extensions they have, and what they are. A `file` property can then name the artifact types it accepts with `artifact`, and `knott validate` reports a value that is not a file of one of them. No wrapper entity per file is needed. `knott artifacts` lists the artifact types, their files and the files nothing points at, and `knott view` draws each artifact type as a node with an arrow from every property that names it. The change is additive.

## Behaviour

### Artifact type files

```markdown
<!-- .knott/artifacts/eval_result.md -->
---
name: eval_result
description: One evaluation run, exported by the harness.
path: artifacts/evals/**
accept: [json]
---
`score` is between 0 and 1. `cases` has one row per test case. Regenerate with `make eval`.
```

- Discovered from `.knott/artifacts/**/*.md`. Subfolders are only for organisation. Other file types are ignored. Artifact type files are loaded on every run, scoped or not.
- An artifact type is identified by its `name`, never by its file name.
- The body is optional guidance for people and agents (what is in the file, how it is made), stored verbatim (`None` when blank). It is never checked against anything.
- Keys are closed:

  | Key | Required | Value |
  |---|---|---|
  | `name` | yes | `^[a-z][a-z0-9_-]*$`. Artifact type names are their own namespace, separate from concepts, relations and connectors. |
  | `description` | no | string |
  | `path` | yes | one folder pattern, or a non-empty list of them, with the syntax and the checks of [0011](0011-entity-location.md) |
  | `accept` | no | a non-empty list of unique extensions, each matching `^[a-z0-9]+$`, as on a `file` property ([0008](0008-file-properties.md)) |

- A missing or invalid `name` is `schema-invalid-field`, and the file defines no artifact type.
- A missing or invalid `path` is `schema-invalid-field`, and the file defines no artifact type: an artifact type without a place would accept every file.
- An invalid `description` or `accept` is `schema-invalid-field`; the artifact type still loads, without that key. Any other key is `schema-invalid-field` with a "did you mean" suggestion.
- A file with no frontmatter, frontmatter that isn't a mapping, or invalid YAML, is `schema-invalid-yaml`.
- Two files with the same `name` are `schema-duplicate-artifact`, reported at the second file in path order and naming both. The first one defines the artifact type.
- An artifact type that no property names is valid. A `path` that no folder matches is valid.

### Which files belong to an artifact type

A file **belongs to** an artifact type when both hold:

1. its folder, as a vault-relative POSIX path, matches at least one pattern of `path`, with regard to case, exactly as an entity's folder is matched in 0011;
2. the artifact type has no `accept`, or the file's extension, as 0008 defines it, is in `accept`.

- Knott never opens the file.
- A file can belong to several artifact types. A file that belongs to none is still a valid value of a `file` property without `artifact`.
- A Markdown file belongs to an artifact type like any other file. An artifact type for data files should declare `accept`, or a `README.md` beside them belongs to it too.

### The `artifact` key

```yaml
# .knott/concepts/experiment.md
properties:
  results:
    type: list
    items: { type: file, artifact: eval_result }
  figure: { type: file, artifact: [plot, diagram] }
```

- `artifact` is allowed on a `file` shape only, wherever `file` is allowed. On any other shape it is `schema-invalid-field` ("only allowed when `type` is file"); on a `list` or `map` the message says to put it on `items` or `values`.
- Its value is one artifact type name, or a non-empty list of unique names.
- A name no artifact type file defines is `schema-unknown-artifact`, one issue per name, at the line of `artifact`. The unknown name is dropped and the others are still enforced. If none is left, values are checked as for a `file` without `artifact`.
- `artifact` and `accept` on the same property are `schema-invalid-field` at the line of `accept`: the artifact type says which extensions it has. The property keeps `artifact`, and `accept` is ignored.
- `artifact` is optional. A `file` without it behaves exactly as in 0008.

### Resolving a value

A value of a property with `artifact` goes through the steps of 0008, in order, and then one more. The first step that fails reports one issue.

- **For a path**, after "a file exists there, with exact case":

  ```
  the file belongs to at least one of the named artifact types   → file-artifact-mismatch
  ```

- **For a URI**, after "a connector has that name": a URI in a property that has at least one known artifact type is `file-artifact-mismatch`. An artifact type is a place in the vault, so a file kept elsewhere is never of an artifact type. A property that takes both vault files and URIs is declared without `artifact`.

The check uses the resolved path, so `../artifacts/evals/run-42.json`, `./run-42.json` and a Markdown link to the same file give the same answer.

### Used and unused files

Knott builds an index of file values to count the files of an artifact type:

- **The files of an artifact type** are the regular files that belong to it, found by walking the vault as discovery does: folders whose name starts with `.` and symlinked folders are not entered. A symbolic link whose real path leaves the vault is not counted.
- **A file is used** when a value at a declared `file` property of some entity, at any depth, resolves to it. The property need not have `artifact`, and the value need not pass the artifact type check: it points at the file.
- Not counted as a use: a key no concept declares, the frontmatter of an entity whose type no concept defines, a `reference` to the file, and a link in a body.
- **An unused file** belongs to an artifact type and is not used. It is never a validation issue ([0014](../decisions/0014-artifact-types-are-places-not-entities.md)).

## Issue codes

| Code | Stage | When | `field` / `line` |
|---|---|---|---|
| `schema-duplicate-artifact` | schema | two artifact type files share a `name` | `name` / its line in the second file |
| `schema-unknown-artifact` | schema | a `file` property's `artifact` names no artifact type | the full key path, e.g. `properties.results.items.artifact` / the line of `artifact` |
| `file-artifact-mismatch` | file | a vault file belongs to none of the property's artifact types, or the value is a URI | the property path / the value's line |

`schema-invalid-field` and `schema-invalid-yaml` also cover artifact type files and the `artifact` key. No existing code changes meaning.

Messages say what was expected and what was found:

```
✗ experiments/exp-7.md:6  results[1]
  file `results[1]`: expects an `eval_result` file (in `artifacts/evals/**`, `.json`), but `../tmp/run-43.json` is in `tmp`

✗ experiments/exp-7.md:7  results[2]
  file `results[2]`: expects an `eval_result` file (in `artifacts/evals/**`, `.json`), but `../artifacts/evals/run-43.csv` is `.csv`

✗ experiments/exp-7.md:8  results[3]
  file `results[3]`: expects an `eval_result` file, but `s3://runs/44.json` is kept outside the vault
```

When the folder and the extension are both wrong, the message names the folder. Several artifact types are joined with `or`. `schema-unknown-artifact` lists the known artifact types and suggests the closest name.

## CLI and API

### `knott validate`

Checks `artifact` for the file values of every in-scope entity. The check needs no index, so a scoped run is as fast as before. Unused files are not reported.

### `knott artifacts`

```
knott artifacts [NAME] [--unused] [--format text|json]
```

Without `NAME`, one line per artifact type, sorted by name: the name, its patterns joined with ` | `, its extensions, and the counts. `· N unused` is left out when it is 0.

```
$ knott artifacts
eval_result  artifacts/evals/**   .json         48 files · 3 unused
plot         img/plots | img/tmp  .png | .svg   12 files
```

With `NAME`, the files of that artifact type, sorted by path, each with the values that use it as `<entity path>  <property path>`. A file used several times has one line per use.

```
$ knott artifacts eval_result
eval_result  48 files · 3 unused
  artifacts/evals/run-01.json   experiments/exp-1.md  results[0]
  artifacts/evals/run-02.json   experiments/exp-1.md  results[1]
                                reports/q3.md         source
  artifacts/evals/run-07.json   (unused)
  …
```

- `--unused` keeps only the artifact types that have unused files, or with `NAME` only the unused files.
- `--format json` prints `{"artifact_types": [{"name", "description", "paths", "accept", "count", "unused", "files": [{"path", "used_by": [{"path", "field"}]}]}]}`. `files` is present only with `NAME`.
- Run it in the vault, as `knott loops`. The whole vault is always read: a use can be anywhere.
- The command does not validate. Schema issues don't stop it; it works with the artifact types and concepts that loaded, as `refs` does.
- Exit `0`. A `NAME` no artifact type defines is exit `2` with `error: no artifact type named <NAME>` and the known names. A vault without artifact types prints `no artifact types (add one to .knott/artifacts/)` and exits `0`.

### `knott types --verbose`

- A `file` property with `artifact` shows it after an arrow, as a reference shows its target: `results  list of file → eval_result`, `figure  file → plot | diagram`. An unknown name is printed `plot (unknown)`.
- An `artifacts:` section after `connectors:` lists every artifact type, sorted by name: the name indented by two spaces, followed by its patterns and extensions; then the description and the guidance indented by four. A vault without artifact types has no `artifacts:` section.

  ```
  artifacts:
    eval_result  artifacts/evals/**  .json
      One evaluation run, exported by the harness.
      `score` is between 0 and 1. `cases` has one row per test case. Regenerate with `make eval`.
  ```

- `knott types NAME` ([0017](0017-types-for-one-type.md)) prints only the artifact types that type's properties name, as it does for connectors.

### `knott view`

An artifact type is a node of its own, so a reader can tell "points at an entity" from "points at a file" by shape alone.

- **The node** is a sheet: a rectangle with one folded corner and a muted fill, where a type is a box. It carries the artifact type's name, its extensions, and `N files`, followed by `· M unused` when `M` is not 0. An artifact type is never abstract and never folded.
- **An edge** is drawn for each `file` property that names an artifact type, one per artifact type, from the type that declares the property to the sheet. It is labelled with the property path and is solid if required, dashed if optional, by the rule of reference edges. With inheritance ([0013](0013-concept-inheritance.md)) it is drawn once, at the declaring type, and at the parent while the family is folded.
- **A `file` property without a known `artifact`** draws no edge, as today. The type that declares it carries one mark, `→ file`, followed by `×N` for several, with a tooltip that lists the property paths. It follows the rules of the `→ any` mark of [0014](0014-open-reference-targets.md), including inheritance and folding.
- **Layouts.** In Layered, the sheets form one column after the last column of types. In Force they take part like any node. In Radial they sit on the outer ring and are never the hub.
- **Hovering** a sheet highlights the types with an edge to it. Hovering a type highlights its sheets with its other neighbours.
- **The header** summary gains `· F artifact types`. A toggle `Artifacts (F)` hides and shows the sheets, their edges and the `→ file` marks. It is on at first, and the page remembers it. The toggle and the summary part are hidden when the vault has no artifact types; the `→ file` marks are then always shown.
- **A sheet's panel** (click it) shows the description, the folders and extensions, the guidance, then:
  - **Used by**: one row per property that names the artifact type, as `<type>.<property path>`.
  - **Unused files: M**, with the hint `knott artifacts <name> --unused` to list them. Left out when `M` is 0. The page holds the count only, never the paths.
- **A type's panel** shows `→ <artifact type>` in the property table, where a reference shows its target, and lists the artifact types under *Artifacts out*, after *References out*.
- **The Outline** ends with a section `Artifacts`: one row per artifact type with its file count. Hovering and clicking a row work as for a type.

**Embedded data.** The page data gains:

- `artifact_types`: a list of `{name, description, guidance, path, paths, accept, count, unused}`, sorted by name. `path` is the artifact type file, `paths` its patterns, and `count` and `unused` are numbers.
- `artifact_edges`: a list of `{source, artifact, path, required}`, one per property and artifact type.
- on each attribute: `artifacts` and `unknown_artifacts`, both `[]` when the property has no `artifact`.

`edges`, `reference_properties` and `referenced_by` are unchanged.

### Python API

- `Ontology.artifact_types: list[ArtifactType(name, description, guidance, path, paths, accept)]`, sorted by name; `[]` for a vault without artifact types. Definitions only: `Knott.ontology()` resolves no file value.
- `Knott.artifacts(name: str | None = None) -> list[ArtifactReport]`. An `ArtifactReport` has `name`, `count`, `unused: list[str]` and `files: list[ArtifactFile(path, used_by: list[FileUse(path, field)])]`. An unknown `name` raises `KnottError`.
- `OntologyAttribute` gains `artifacts: list[str]` and `unknown_artifacts: list[str]`, both `[]` by default.
- `ArtifactType`, `ArtifactReport`, `ArtifactFile` and `FileUse` are exported from `knott`.

### Agent skill

To add to the bundled skill when this is implemented:

- `→ <artifact type>` on a `file` property in `knott types --verbose` means the value must be a file of that artifact type. Read the artifact type under `artifacts:` to see where such files are stored and what they hold.
- Put a new file of an artifact type in a folder its `path` matches, with one of its extensions, then name it from the entity.
- `knott artifacts --unused` lists files that no entity points at. They are not errors: link them, or leave them.
- Do not write a wrapper entity for a file of an artifact type unless that file needs properties of its own.

## Edge cases

| Case | Result |
|---|---|
| `artifact: eval_result`, value `../artifacts/evals/run-42.json` | valid |
| the same value written `"[run 42](../artifacts/evals/run-42.json)"` | valid; the label is ignored |
| `path: artifacts/evals`, file at `artifacts/evals/2026/run.json` | `file-artifact-mismatch`; write `artifacts/evals/**` to allow subfolders |
| `accept: [json]`, file `run-42.JSON` in the right folder | valid; extensions compare without regard to case |
| `path: Artifacts/evals`, the folder on disk is `artifacts/evals` | `file-artifact-mismatch`, also on a file system that ignores case |
| the file is missing | `file-not-found`; the artifact type is not checked |
| `artifact: eval_result`, value `s3://runs/44.json`, `s3` declared | `file-artifact-mismatch`: kept outside the vault |
| `artifact: eval_result`, value `s4://runs/44.json`, no such connector | `file-unknown-connector`, the earlier step |
| `artifact: [plot, diagram]`, the file belongs to `diagram` only | valid |
| `artifact: [plot, plt]`, no artifact type `plt` | `schema-unknown-artifact` for `plt`; values must be a `plot` |
| `artifact: plt`, no artifact type `plt` | `schema-unknown-artifact`; any vault file or declared URI passes |
| `artifact: []` | `schema-invalid-field` |
| `{ type: file, artifact: plot, accept: [png] }` | `schema-invalid-field` at `accept`; the property keeps `artifact` |
| `{ type: string, artifact: plot }` | `schema-invalid-field`: only allowed when `type` is file |
| an artifact type file without `path` | `schema-invalid-field`; it defines no artifact type, and properties that name it get `schema-unknown-artifact` |
| two artifact types with the same `path` and `accept` | valid; every file there belongs to both |
| an artifact type with `path: .cache/**` | values in `.cache/` pass the artifact type check; its files are not counted and never listed as unused, because the walk skips hidden folders |
| an artifact type without `accept`, a `README.md` in its folder | the README belongs to the artifact type and is listed as unused |
| an entity file in an artifact type's folder | belongs to the artifact type like any file; it is unused unless a `file` property names it |
| two entities name the same file | valid; `knott artifacts NAME` prints both uses |
| a `file` property without `artifact` names a file of an artifact type | valid, and the file is used |
| a `reference` names a Markdown file that belongs to an artifact type | not a use; only `file` values count |
| a file named only in an undeclared key or in a body link | unused |
| an artifact type with no files | `0 files`; the sheet is still drawn |

## Out of scope

- Artifact types for files behind a connector. A later spec could let an artifact type name the connectors it accepts.
- Checking what is in a file: a JSON schema, a media type, a size.
- A `filename` pattern on an artifact type, as [0012](0012-entity-file-names.md) gives concepts. The folder and the extension decide.
- Properties, a `kid` or an identity for a file. A file that needs them gets a wrapper entity ([0012](../decisions/0012-files-are-property-values.md)).
- A `reference` to a file that is not Markdown.
- Reporting an unused file, or a file in an artifact type's folder with the wrong extension, as a validation issue.
- `knott refs` on a file path, and listing the values of `file` properties that have no artifact type.
- Moving or renaming a file that is not Markdown ([0018](0018-move-entities.md) moves Markdown files only).
- Inheritance between artifact types.

## Compatibility

Additive. A `file` property with an `artifact` key got `schema-invalid-field` before and is now checked against the artifact type. A vault without `.knott/artifacts/` behaves as before, with one visible change in `knott view`: a type with `file` properties gains the `→ file` mark. Ontology API and view data additions only. One new command, `knott artifacts`. Version 0.16.0. Number 0019 is the included-folders spec on the `feat/mv` branch, which takes 0.15.0; with it, "walking the vault as discovery does" follows its `include` rules.
