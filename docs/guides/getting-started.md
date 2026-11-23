---
type: guide
title: Getting started
audience: human
concepts:
  - "[Vault](../concepts/vault.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Relation](../concepts/relation.md)"
commands:
  - "[knott init](../commands/init.md)"
  - "[knott validate](../commands/validate.md)"
---
# Getting started

**1. Create a vault.**

```sh
mkdir my-vault && cd my-vault && uvx knott init
```

**2. Define two types.** Each type is a Markdown file in `.knott/concepts/`. `.knott/concepts/script.md`:

```markdown
---
name: script
properties:
  title:
    type: string
    required: true
---
```

`.knott/concepts/transcript.md`, with a reference to a script and a template for the body:

```markdown
---
name: transcript
properties:
  derived_from:
    type: reference
    target: script
---
# Transcript

<!-- Who speaks, and what the recording covers. -->
```

**3. Write entities**, anywhere you like. `scripts/foo.md`:

```markdown
---
type: script
title: Episode 42
---
# Episode 42
```

`transcripts/foo.md`:

```markdown
---
type: transcript
derived_from: "[Episode 42](../scripts/foo.md)"
---
# Transcript
```

**4. Validate.**

```sh
$ uvx knott validate
✓ 2 schemas
✓ 2 entities
✓ 1 relation
✓ vault is valid
```

**5. Break something on purpose.** Change `scripts/foo.md` to `title: no`, run `knott validate`, and read the error: it explains that unquoted `no` is a boolean and suggests quoting it. Every issue code has a page in [`issues/`](../issues/).

Upgrading a vault made before 0.5, with a `.knott/schemas/` folder? Run [`knott migrate`](../commands/migrate.md).

Next: [Writing schemas](writing-schemas.md), [Using Obsidian](obsidian.md).
