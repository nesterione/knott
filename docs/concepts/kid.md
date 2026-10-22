---
type: concept
title: Kid
summary: The knott-managed identity of an entity, a lowercase UUID under the reserved `kid` key, which survives moves and renames.
spec_section: "§12"
related:
  - "[Entity](entity.md)"
  - "[Reference resolution](reference-resolution.md)"
  - "[Schema](schema.md)"
---
# Kid

A **kid** ("knott id") identifies an entity independently of its file path:

```yaml
---
type: lexeme
kid: 3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21
lemma: restoranas
---
```

- **Reserved.** `kid` is a top-level frontmatter key owned by knott, like `type`. A schema can't declare a field named `kid` (a field inside an `object` attribute can).
- **Format.** A canonical lowercase UUID: `8-4-4-4-12` hex digits, any version. Uppercase or `{…}` forms are rejected, and the message gives the lowercase form.
- **Unique** across the whole vault, whatever the type. A duplicate is reported once, naming every file that claims it.
- **Optional** unless the type's schema says `kid: required`.

## Getting one

Don't invent one by hand. Run:

```sh
knott validate --fix [PATH...]
```

Every checked entity without a `kid` key gets `kid: <new uuid>`, inserted as one line after `type:`. Nothing else in the file changes. An entity whose `kid` is present but empty or invalid is left for you to fix, and so is a duplicate.

**Copying a file copies its `kid`.** Delete the `kid:` line from the copy, then run `--fix`.

## Referring to it

```yaml
includes:
  - "[Draugas](../lexemes/draugas.md)"            # default: a clickable Markdown link
  - kid:3f2b8c1e-9d4a-4c2e-b7f1-0a6d5e9c8b21      # survives moves and renames
```

A `kid:` reference is checked like a path: the entity exists, and its type matches the relation's `target`. It must be written on its own, not inside a Markdown link. See [Reference resolution](reference-resolution.md).

A `kid` does **not** stop two files from describing the same concept; each just gets its own `kid`. See [decision 0009](../decisions/0009-kid-identity.md).
