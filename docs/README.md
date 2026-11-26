# Knott documentation

This folder is itself a **Knott vault**: the documentation is written as typed Markdown entities, validated by Knott. It doubles as a worked example of an ontology.

```sh
cd docs
knott types --verbose   # the documentation types, with their body templates and relations
knott validate          # every page and link is checked
```

This README has no frontmatter, so Knott treats it as an ordinary note.

## Start here

- [Getting started](guides/getting-started.md)
- [Ontology](concepts/ontology.md): how this folder is modeled, and how to design your own

## Concepts

[Vault](concepts/vault.md) · [Entity](concepts/entity.md) · [Frontmatter](concepts/frontmatter.md) · [Schema](concepts/schema.md) · [Attribute](concepts/attribute.md) · [File](concepts/file.md) · [Relation](concepts/relation.md) · [Reference resolution](concepts/reference-resolution.md) · [Kid](concepts/kid.md) · [Loop](concepts/loop.md) · [Issue](concepts/issue.md) · [Ontology](concepts/ontology.md)

## Guides

- [Getting started](guides/getting-started.md)
- [Writing schemas](guides/writing-schemas.md)
- [Using a vault in Obsidian](guides/obsidian.md)
- [Agent workflow](guides/agent-workflow.md)
- [Python API](guides/python-api.md)

## Commands

[init](commands/init.md) · [validate](commands/validate.md) · [types](commands/types.md) · [migrate](commands/migrate.md) · [version](commands/version.md) · [skill](commands/skill.md) · [view](commands/view.md) · [refs](commands/refs.md) · [list](commands/list.md) · [show](commands/show.md) · [loops](commands/loops.md)

## Issue codes

| Stage | Codes |
|---|---|
| schema | [schema-invalid-yaml](issues/schema-invalid-yaml.md) · [schema-invalid-field](issues/schema-invalid-field.md) · [schema-duplicate-type](issues/schema-duplicate-type.md) · [schema-unknown-target](issues/schema-unknown-target.md) · [schema-legacy-layout](issues/schema-legacy-layout.md) · [schema-duplicate-relation](issues/schema-duplicate-relation.md) · [schema-duplicate-connector](issues/schema-duplicate-connector.md) · [schema-duplicate-loop](issues/schema-duplicate-loop.md) · [schema-unknown-parent](issues/schema-unknown-parent.md) · [schema-extends-cycle](issues/schema-extends-cycle.md) · [schema-property-redefined](issues/schema-property-redefined.md) · [loop-invalid-target](issues/loop-invalid-target.md) · [relation-unknown](issues/relation-unknown.md) · [relation-inverse-conflict](issues/relation-inverse-conflict.md) · [relation-symmetric-mismatch](issues/relation-symmetric-mismatch.md) |
| entity | [entity-invalid-frontmatter](issues/entity-invalid-frontmatter.md) · [entity-unknown-type](issues/entity-unknown-type.md) · [not-an-entity](issues/not-an-entity.md) · [entity-misplaced](issues/entity-misplaced.md) · [entity-invalid-name](issues/entity-invalid-name.md) · [entity-abstract-type](issues/entity-abstract-type.md) · [loop-stage-unmet](issues/loop-stage-unmet.md) |
| kid | [kid-missing](issues/kid-missing.md) · [kid-invalid](issues/kid-invalid.md) · [kid-duplicate](issues/kid-duplicate.md) |
| attribute | [attribute-missing](issues/attribute-missing.md) · [attribute-type-mismatch](issues/attribute-type-mismatch.md) · [attribute-unknown-field](issues/attribute-unknown-field.md) · [attribute-unknown-option](issues/attribute-unknown-option.md) |
| relation | [relation-missing](issues/relation-missing.md) · [relation-invalid-value](issues/relation-invalid-value.md) · [relation-target-outside-vault](issues/relation-target-outside-vault.md) · [relation-target-not-found](issues/relation-target-not-found.md) · [relation-target-not-entity](issues/relation-target-not-entity.md) · [relation-target-type-mismatch](issues/relation-target-type-mismatch.md) · [relation-target-ambiguous](issues/relation-target-ambiguous.md) · [relation-cycle](issues/relation-cycle.md) |
| file | [file-missing](issues/file-missing.md) · [file-invalid-value](issues/file-invalid-value.md) · [file-unknown-connector](issues/file-unknown-connector.md) · [file-outside-vault](issues/file-outside-vault.md) · [file-not-found](issues/file-not-found.md) · [file-extension-mismatch](issues/file-extension-mismatch.md) |

## Design decisions

1. [Markdown files are the source of truth](decisions/0001-markdown-is-source-of-truth.md)
2. [Relations use relative paths, not IDs](decisions/0002-relative-paths-not-ids.md)
3. [Relations are stored only on the source side](decisions/0003-source-side-relations.md)
4. [Strict attribute typing, including YAML 1.1 booleans](decisions/0004-strict-typing.md)
5. [What counts as an empty value](decisions/0005-empty-values.md)
6. [Symlinks cannot take a relation outside the vault](decisions/0006-symlinks-and-containment.md)
7. [Hostile YAML is reported, never crashes or hangs](decisions/0007-parser-robustness.md)
8. [Structured attributes use explicit keywords, and objects are closed](decisions/0008-structured-attributes.md)
9. [Entities get a knott-managed `kid`](decisions/0009-kid-identity.md)
10. [Concepts are Markdown files, and references are properties](decisions/0010-concept-files-and-reference-properties.md)
11. [Changes are specified in frozen specs, wanted ones start as intents](decisions/0011-specs-intents-and-frozen-history.md)
12. [Files are values of a `file` property, and a URI names files kept elsewhere](decisions/0012-files-are-property-values.md)
13. [A command may edit files when the edit adds no knowledge](decisions/0013-commands-may-make-mechanical-edits.md)

## How changes are made

Wanted work starts as an **intent** in [intents/](intents/): the need, an example, open questions. When we pick it up, a **spec** in [specs/](specs/) defines the exact behaviour, citing the **decisions** that explain why. Implementing a spec updates [SPEC.md](../SPEC.md) (the current state) and these docs. Once implemented, a spec is never edited again; a later change writes a new spec that `amends` or `supersedes` it. See [decision 0011](decisions/0011-specs-intents-and-frozen-history.md).

### Specs

1. [Add `knott view` to draw the ontology as an HTML page](specs/0001-ontology-viewer.md)
2. [Ship the agent skill in the package and add `knott skill install`](specs/0002-skill-install-command.md)
3. [Add list, object and map attributes](specs/0003-structured-attributes.md)
4. [Give entities a knott-managed `kid`](specs/0004-kid-identity.md)
5. [Define types in concept files, with references as properties](specs/0005-concept-files.md)
6. [Relation definitions and reverse lookup](specs/0006-relation-definitions.md)
7. [The view's Relations panel lists inline relations](specs/0007-view-inline-relations.md)
8. [File properties and connectors](specs/0008-file-properties.md)
9. [Enum properties](specs/0009-enum-properties.md)
10. [Loops](specs/0010-loops.md)
11. [Entity location](specs/0011-entity-location.md)
12. [Entity file names](specs/0012-entity-file-names.md)
13. [Concept inheritance](specs/0013-concept-inheritance.md)
14. [Open reference targets](specs/0014-open-reference-targets.md)
15. [Type tree](specs/0015-type-tree.md)
16. [List and show entities](specs/0016-list-and-show-entities.md)
17. [Show the details of one type](specs/0017-types-for-one-type.md)
18. [Move a file and rewrite the links to it](specs/0018-move-entities.md)
19. [Included folders](specs/0019-included-folders.md)

### Intents

- [Relation definitions](intents/relation-definitions.md)
- [File properties](intents/file-properties.md)
- [Remote sources](intents/remote-sources.md)
- [Enumerated values](intents/enumerated-values.md)
- [Loops](intents/loops.md)
- [Entity location](intents/entity-location.md)
- [Entity file names](intents/entity-file-names.md)
- [Concept inheritance](intents/concept-inheritance.md)
- [Open reference targets](intents/open-reference-targets.md)
- [Type tree](intents/type-tree.md)
- [Read the vault as data](intents/read-the-vault-as-data.md)
- [Move a file without breaking links](intents/move-without-breaking-links.md)
- [Included folders](intents/included-folders.md)
