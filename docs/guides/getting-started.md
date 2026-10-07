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

**2. Define two types.** `.knott/schemas/script.yaml`:

```yaml
type: script
attributes:
  title:
    type: string
    required: true
```

`.knott/schemas/transcript.yaml`:

```yaml
type: transcript
relations:
  derived_from:
    target: script
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

Next: [Writing schemas](writing-schemas.md), [Using Obsidian](obsidian.md).
