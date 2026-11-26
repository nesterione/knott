---
type: decision
title: A command may edit files when the edit adds no knowledge
status: accepted
decided_on: 2026-11-26
affects:
  - "[Entity](../concepts/entity.md)"
  - "[Relation](../concepts/relation.md)"
  - "[Reference resolution](../concepts/reference-resolution.md)"
  - "[Vault](../concepts/vault.md)"
amends:
  - "[0009](0009-kid-identity.md)"
---
# 0013: A command may edit files when the edit adds no knowledge

**Context.** [0001](0001-markdown-is-source-of-truth.md) makes the files the source of truth, and [0009](0009-kid-identity.md) calls the `kid` insert "knott's only edit to user files". The agent guide says files are the interface: there is no `create` command. One routine operation fits this badly. Moving or renaming a file means rewriting every link to it, each a path relative to a different folder, plus the moved file's own links. Knott already knows every one of those links; an agent doing it by hand runs `knott refs`, edits N files, and still misses the links in bodies.

**Decision.**

1. **A command may edit the vault's Markdown files when everything it writes follows from what the vault already says.** Giving an entity a `kid` and rewriting link paths after a move are such edits: they record no new fact, and there is one right result.
2. **A command never writes knowledge.** No command sets a property value an author would have to choose, writes prose in a body, or picks a type. Those stay ordinary file edits. This decision does not approve a command that creates an entity or sets a property; each needs its own decision.
3. **A mechanical edit changes only the characters it must.** Every edited file is parsed again and compared with the expected result before anything is written. If one file fails, nothing is written.
4. **No command is required.** Everything a command does can be done by hand, and `knott validate` judges the result the same way.
5. **Knott still gives the body no meaning.** It does not check bodies or report on them. A move rewrites the destinations of Markdown links in bodies and nothing else there, because a move that leaves them broken is not finished and `validate` would not notice.

**Not included.** A command that deletes an entity. Moving folders or files that are not Markdown. Keeping an index or any state between runs; 0001 stands.

**Why.**

- **Mechanical, not authored:** the risk [0001](0001-markdown-is-source-of-truth.md) guards against is knowledge that lives in a tool. A rewritten relative path carries none; the file after the move says what it said before.
- **The tool is better placed than the agent:** it resolves every reference already, in every form. By hand, the cost grows with the number of links and one miss leaves the vault broken.
- **Bodies too:** in this folder, spec 0006 was referenced three times from frontmatter and linked four times from bodies and `README.md`. A move that fixed only declared references would report success and leave more than half of the links dead.
- **A narrow rule, not "commands may write":** each write command is a place where knott's idea of a file can drift from the author's. Naming the test (no new knowledge, one right result) keeps the next proposal honest.

**Consequences.** `knott mv` exists ([spec 0018](../specs/0018-move-entities.md)). The sentence in 0009 that the `kid` insert is the only edit no longer holds; the rest of 0009 stands. The command page's `writes_files` is `true` for a second command. The agent skill tells agents to move files with `knott mv`.
