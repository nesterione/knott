---
type: guide
title: Agent workflow
audience: agent
concepts:
  - "[Schema](../concepts/schema.md)"
  - "[Entity](../concepts/entity.md)"
  - "[Issue](../concepts/issue.md)"
commands:
  - "[knott types](../commands/types.md)"
  - "[knott validate](../commands/validate.md)"
---
# Agent workflow

Knott is built for agents that persist knowledge as files. The full instructions ship as an Agent Skill (install it into a project with `knott skill install`). This is the short version.

1. `knott types --verbose`: find the right type and its schema file.
2. Read the schema YAML: `description`, required fields, relation targets.
3. Create or edit the Markdown file directly. Knott has no `create` command; files are the interface.
4. Write relations as quoted Markdown links with paths relative to the file.
5. `knott validate <file> --format json`
6. Fix every issue and re-validate until `ok` is `true`.

## Reading results

```json
{
  "ok": false,
  "stats": {"schemas": 5, "entities": 1, "relations": 0},
  "issues": [{
    "code": "relation-target-not-found",
    "path": "guides/new.md",
    "line": 7,
    "field": "concepts",
    "message": "relation `concepts`: `../concept/vault.md` does not exist (resolved to `concept/vault.md`)"
  }]
}
```

Branch on `code` (stable), show `message` (human-readable). The `issues/` folder documents every code with cause and fix.

## Rules of thumb

- Never edit `.knott/schemas/` to make an entity pass unless asked. The schema is the contract.
- Never delete a required field or relation to silence an error. Find the right value.
- Never add an inverse relation on the target. Relations live on the source only.
