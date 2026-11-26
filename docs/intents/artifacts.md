---
type: intent
title: Artifacts
status: open
raised_on: 2026-11-26
concepts:
  - "[File](../concepts/file.md)"
  - "[Schema](../concepts/schema.md)"
  - "[Ontology](../concepts/ontology.md)"
---
# Artifacts

## Need

A vault holds files that are not Markdown and that come in recognisable kinds: evaluation results exported as JSON, figures, recordings. A [file property](../concepts/file.md) can point at one, but it only says "a file", optionally with an extension. Nothing says what kind of JSON it is, where such files live, or how they are made. To give a file a meaning today, the vault needs a concept and one Markdown wrapper per file. For uniform, machine-made files that wrapper is overhead: it repeats the same description and carries nothing of its own.

Three things are missing:

- a place to describe a kind of file once, for people and agents;
- a check that a property which expects that kind is given one, as a reference checks the type of its target;
- a way to see the files of a kind that nothing points at, and to see these kinds in `knott view`, where a file property draws nothing today.

## Example

An experiments vault:

- `artifacts/evals/` holds one JSON file per evaluation run, written by a script.
- The vault describes `eval_result` once: these files are in `artifacts/evals/`, they are `.json`, and the text says what the fields mean and how to regenerate them.
- An `experiment` entity lists its runs in `results`. A value that points at a PNG, or at a JSON file in another folder, is reported.
- `knott view` shows `eval_result` as a node of its own, with an arrow from `experiment`, the number of files, and how many no experiment points at.
- A file that needs its own title, author or status still gets a wrapper entity. Both ways work in one vault.

## Open questions

Answered by [spec 0020](../specs/0020-artifact-types.md). Left for a later spec:

- Whether an artifact type can also cover files kept elsewhere, behind a connector.
- Whether an artifact type can check what is in a file, such as a JSON schema.
- Moving or renaming a file that is not Markdown and rewriting the values that name it.
