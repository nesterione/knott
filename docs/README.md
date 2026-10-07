# Knott documentation

This folder is itself a **Knott vault**: the documentation is written as typed Markdown entities, validated by Knott. It doubles as a worked example of an ontology.

```sh
cd docs
knott types --verbose   # the five documentation types
knott validate          # every page and link is checked
```

This README has no frontmatter, so Knott treats it as an ordinary note.

## Start here

- [Getting started](guides/getting-started.md)
- [Ontology](concepts/ontology.md): how this folder is modeled, and how to design your own

## Concepts

[Vault](concepts/vault.md) · [Entity](concepts/entity.md) · [Frontmatter](concepts/frontmatter.md) · [Schema](concepts/schema.md) · [Attribute](concepts/attribute.md) · [Relation](concepts/relation.md) · [Reference resolution](concepts/reference-resolution.md) · [Issue](concepts/issue.md) · [Ontology](concepts/ontology.md)

## Guides

- [Getting started](guides/getting-started.md)
- [Writing schemas](guides/writing-schemas.md)
- [Using a vault in Obsidian](guides/obsidian.md)
- [Agent workflow](guides/agent-workflow.md)
- [Python API](guides/python-api.md)

## Commands

[init](commands/init.md) · [validate](commands/validate.md) · [types](commands/types.md) · [version](commands/version.md)

## Issue codes

| Stage | Codes |
|---|---|
| schema | [schema-invalid-yaml](issues/schema-invalid-yaml.md) · [schema-invalid-field](issues/schema-invalid-field.md) · [schema-duplicate-type](issues/schema-duplicate-type.md) · [schema-unknown-target](issues/schema-unknown-target.md) · [schema-field-conflict](issues/schema-field-conflict.md) |
| entity | [entity-invalid-frontmatter](issues/entity-invalid-frontmatter.md) · [entity-unknown-type](issues/entity-unknown-type.md) · [not-an-entity](issues/not-an-entity.md) |
| attribute | [attribute-missing](issues/attribute-missing.md) · [attribute-type-mismatch](issues/attribute-type-mismatch.md) |
| relation | [relation-missing](issues/relation-missing.md) · [relation-invalid-value](issues/relation-invalid-value.md) · [relation-target-outside-vault](issues/relation-target-outside-vault.md) · [relation-target-not-found](issues/relation-target-not-found.md) · [relation-target-not-entity](issues/relation-target-not-entity.md) · [relation-target-type-mismatch](issues/relation-target-type-mismatch.md) |

## Design decisions

1. [Markdown files are the source of truth](decisions/0001-markdown-is-source-of-truth.md)
2. [Relations use relative paths, not IDs](decisions/0002-relative-paths-not-ids.md)
3. [Relations are stored only on the source side](decisions/0003-source-side-relations.md)
4. [Strict attribute typing, including YAML 1.1 booleans](decisions/0004-strict-typing.md)
5. [What counts as an empty value](decisions/0005-empty-values.md)
6. [Symlinks cannot take a relation outside the vault](decisions/0006-symlinks-and-containment.md)
7. [Hostile YAML is reported, never crashes or hangs](decisions/0007-parser-robustness.md)
