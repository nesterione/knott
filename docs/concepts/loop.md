---
type: concept
title: Loop
summary: A loop is a repeated process that entities of one type pass through; it follows one enum property and says what each stage needs.
spec_section: "§27"
related:
  - "[Attribute](attribute.md)"
  - "[Relation](relation.md)"
  - "[Schema](schema.md)"
  - "[Ontology](ontology.md)"
---
# Loop

A **loop** is a process a vault repeats: producing an episode, taking a spec from draft to implemented, writing a post. Every entity of the loop's type is one pass through it. The loop follows one `enum` property of the type; the property's value is the entity's **stage**. For each stage the loop lists what it **needs**: properties that are set, and entities that point at this one.

```markdown
<!-- .knott/loops/episode-production.md -->
---
name: episode-production
description: From an episode idea to a published episode.
type: episode
property: status
stages:
  idea:
  planned:   { needs: [participants] }
  recorded:  { needs: [recorded_at, materials: transcript] }
  published: { needs: [published_at, links, materials: [summary, topics]] }
---

A loop on a type follows its [subtypes](schema.md#inheritance) too: an entity of a subtype is placed and checked like any other, and a need `<inverse>: <type>` is met by an entity of a subtype of that type. Two loops on the same property, one on a type and one on its subtype, are [`schema-duplicate-loop`](../issues/schema-duplicate-loop.md).
## recorded

Export the transcript into the episode folder, then run the review.
```

- **One file per loop**, in `.knott/loops/`, in subfolders if you like. A vault can have many loops.
- **One property per loop.** Two loops can follow different properties of one type, never the same one.
- **Describe and check.** Knott never changes a stage and never creates a file.
- **Needs add up.** An entity at a stage must meet the needs of that stage and of every stage before it.
- **Only existence.** A need checks that something is there, never its value.

## Stages and side exits

The keys of `stages` are options of the enum, and the order they are written in is the **path**. An option the loop leaves out is a **side exit**, such as `dropped` or `superseded`: it has no needs and no next stage. An entity whose property is empty, or not an option, has **no stage**.

## Needs

A need is one of two things:

- **A property name**, such as `recorded_at`. It is met when the property is set and not empty, by the rules of [decision 0005](../decisions/0005-empty-values.md).
- **`<inverse>: <type>`**, such as `materials: transcript`. `materials` is the `inverse` of a [relation](relation.md). The need is met when at least one `transcript` has a reference that names that relation and points at this entity. A list, `materials: [summary, topics]`, needs one of each.

A plain reference that names no relation can't be used in a need: give it a relation file with an `inverse` first.

## Claimed stage and next stage

An entity that sits at a stage without meeting its needs is wrong: [`loop-stage-unmet`](../issues/loop-stage-unmet.md), reported by `knott validate`. An entity that doesn't meet the needs of the *next* stage yet is work in progress and stays valid. [`knott loops`](../commands/loops.md) and the board in [`knott view`](../commands/view.md) show what it still misses.

So the way to move an entity forward is: add what the next stage needs, then change the property.

## Guidance

The body of the loop file is guidance for whoever does the work. A line `## <stage>` starts the guidance for that stage or side exit; the text before the first such line is about the loop as a whole. `knott types --verbose`, `knott loops --format json` and the view show it. Knott never checks it.

## Not supported

A stage worked out from links and not stored, a process that crosses types, needs on values or counts, alternatives ("a transcript or a script"), rules on which stage may follow which, and history of stage changes. See [spec 0010](../specs/0010-loops.md).
