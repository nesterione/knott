---
type: decision
title: An artifact type is a place in the vault, not an entity
status: proposed
decided_on: 2026-11-26
affects:
  - "[File](../concepts/file.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Entity](../concepts/entity.md)"
---
# 0014: An artifact type is a place in the vault, not an entity

**Context.** [0012](0012-files-are-property-values.md) made a file a value of a `file` property and kept the Markdown file as the entity. A vault that wants typed files defines a concept with a required `file` property and writes one wrapper entity per file. For uniform, machine-made files (one JSON per evaluation run) the wrapper repeats the same words and carries nothing of its own. See the [artifact types](../intents/artifacts.md) intent.

**Decision.**

1. **An artifact type is defined once**, in a Markdown file in `.knott/artifacts/`: a name, a description, guidance, the folders its files are stored in, and optionally their extensions.
2. **A file belongs to an artifact type by where it is and what its extension is.** Knott does not open it and keeps no list of members.
3. **A `file` property can name the artifact types it accepts** with `artifact`, as a `reference` names its `target`. A value that is not a file of one of them is an error.
4. **A file of an artifact type is still a value, never an entity.** It has no `type`, no `kid` and no properties, and a `reference` cannot point at it. 0012 is unchanged.
5. **A file that nothing points at is information, not an error.** Knott shows it in `knott artifacts` and `knott view`; `knott validate` does not report it.

**Not included.** Files behind a connector: an artifact type is a place in the vault, and knott cannot see a file kept elsewhere. Checking a file's content. Moving a file that is not Markdown.

**Why.**

- **Location, not a sidecar or a registry:** a sidecar per file is the wrapper under another name, and a list of members goes stale the moment a script writes a new file. A folder and an extension are facts knott can read from the file system without opening anything.
- **Location, not content:** telling two kinds of JSON apart by reading them means parsing every file and defining a schema language. Concepts already say where entities live ([spec 0011](../specs/0011-entity-location.md)); artifact types reuse that rule and its pattern syntax.
- **Not an entity:** a JSON file has no frontmatter, so it cannot hold a `type`, a `kid` or references of its own. Giving it an identity by path would break on rename, the reason 0012 rejected "the file is the entity".
- **A key on the property, not a new shape:** `file` with `artifact` is to `file` what `reference` with a named target is to `target: any`. Every rule of spec 0008 about value forms and nesting keeps applying.
- **Unused files are not errors:** a script may write files before any entity names them. An error would tell an agent to fix something that is not broken.

**Consequences.**

- `.knott/` gains a fifth folder of definitions, `artifacts/`.
- Two artifact types that share a folder and an extension cannot be told apart. They need separate folders.
- A file that needs its own title, status or links still needs a wrapper entity.
- Knott resolves every file value in the vault to count the files of an artifact type and find the unused ones. This is the index that spec 0008 left for later.
