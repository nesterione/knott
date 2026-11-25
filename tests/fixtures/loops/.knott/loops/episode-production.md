---
name: episode-production
description: From an episode idea to a published episode.
type: episode
property: status
stages:
  idea:
  planned:   { needs: [participants] }
  recorded:  { needs: [recorded_at, materials: transcript] }
  published: { needs: [published_at, links, materials: [summary, transcript]] }
---
Tasks live in GitHub Issues.

## recorded

Export the transcript into the episode folder.

## dropped

Say why in the body.
