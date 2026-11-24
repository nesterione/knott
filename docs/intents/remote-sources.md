---
type: intent
title: Remote sources
status: open
raised_on: 2026-11-24
concepts:
  - "[Entity](../concepts/entity.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Vault](../concepts/vault.md)"
---
# Remote sources

## Need

Some entities have a counterpart in another system. A guide written in the vault is published to the wiki. A page written in the wiki is copied into the vault so agents can read it. Today nothing in a concept says which of these a type is, so an agent can't tell a page it may edit from a copy that the next sync overwrites, and each sync script invents its own frontmatter keys for the remote address and the last synced revision.

## Example

A team vault:

- `wiki_page` entities are written in the vault and pushed to the wiki. After a push, the entity records the page's address and revision. Editing the body afterwards makes it "changed since the last sync", which a connector reads as "push this".
- `handbook_page` entities are pulled from the wiki. Their bodies are copies. An agent that reads the concept knows not to edit them.
- Two entities that claim the same remote page are reported by `knott validate`.

A document that the vault only points at, without a copy, needs none of this: it is an entity with a `file` property whose value is a URI ([file properties](file-properties.md)).

## Direction

Agreed on 2026-11-24, for the spec to build on:

- Knott describes, a connector executes. Knott ships no sync command and no connectors. An agent skill or a script does the transfer and writes the result into the entity; knott validates what it wrote.
- The source and the direction (push, pull or both) are declared on the concept, the same for every entity of the type.
- The sync state (address, revision, time, content hash) lives in the entity's frontmatter under a reserved key that only connectors write. Knott keeps no state file.
- Two-way sync is three detectable states: only the vault changed, only the remote changed, or both changed. Knott defines no merging.

## Open questions

- Decision 0001 says Markdown files are the source of truth. A pulled body is a dated copy of something else. The spec needs a decision that amends 0001.
- The exact keys of the concept's source declaration and of the entity's reserved block, and whether the remote address is a connector URI as in [file properties](file-properties.md).
- How "changed since the last sync" is reported. It is the normal state before a push, so it must not be a validation error that an agent is told to fix.
- What the content hash covers: the body alone, or the body and declared properties.
- Whether a type may later allow several sources, with each entity picking one.
