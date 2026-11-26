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
  - "[knott refs](../commands/refs.md)"
---
# Agent workflow

Knott is built for agents that persist knowledge as files. The full instructions ship as an Agent Skill (install it into a project with `knott skill install`). This is the short version.

1. `knott types --tree` for the overview (which types exist, which are kinds of which, how many entities each has), then `knott types --verbose`: find the right type and its concept file. The `relations:` section at the end says what each link means; when two properties fit, its guidance says which one to use.
2. Pick the most specific type that fits; a type marked `abstract: yes` cannot be used, take one of its `subtypes`. Read the concept file in `.knott/concepts/`: `description`, required properties, reference targets, and the body template.
3. Create or edit the Markdown file directly, in a folder the type's `path:` line allows when `knott types --verbose` shows one, and under a name its `filename:` pattern allows. Knott has no `create` command; files are the interface. Start a new body from the template and delete each `<!-- -->` comment once its section is written.
4. Write references as quoted Markdown links with paths relative to the file. A `reference` holds one; a `list` of references needs a list, even for one.
5. `knott validate <file> --fix --format json`. `--fix` gives a new entity its [kid](../concepts/kid.md); it never changes an existing one.
6. Fix every issue and re-validate until `ok` is `true`.

When starting a new entity from a copy of another file, delete the copied `kid:` line first, or both files claim the same `kid`.

Before renaming, deleting or replacing an entity, run `knott refs <file>` to see who links to it, and update those files too.

Before changing a property that a [loop](../concepts/loop.md) follows (often `status`), run `knott loops <name>`: it lists what each entity's next stage still needs. Add those first, then change the property. Setting a stage whose needs are not met is [`loop-stage-unmet`](../issues/loop-stage-unmet.md).

If every command reports only `schema-legacy-layout`, the vault predates 0.5. Run `knott migrate` and show the diff to the user.

## Reading results

```json
{
  "ok": false,
  "stats": {"schemas": 5, "entities": 1, "relations": 0},
  "issues": [{
    "code": "relation-target-not-found",
    "path": "guides/new.md",
    "line": 7,
    "field": "concepts[0]",
    "message": "relation `concepts[0]`: `../concept/vault.md` does not exist (resolved to `concept/vault.md`)"
  }]
}
```

Branch on `code` (stable), show `message` (human-readable). The `issues/` folder documents every code with cause and fix.

## Rules of thumb

- Never edit `.knott/concepts/` to make an entity pass unless asked. The concept file is the contract.
- Never delete a required field or relation to silence an error. Find the right value.
- Never add an inverse reference on the target. References live on the source only. An `inverse` such as `superseded_by` is how `knott refs` labels incoming links, not a property to write.
- Store a `symmetric` link, such as `related`, on one side only.
