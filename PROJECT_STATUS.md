# Project Status

Last explanatory handoff update: **2026-08-15**

This file is context. Live GitHub state and `config/tracepixel.core-lane.json` are operational authority.

## Product rule

> Humans define intent and judge the result. AI owns the iteration in between.

> Deterministic where possible. Multimodal where necessary. Human judgment at the end.

TracePixel is an independent research/production-tool project for agent-authored, deterministic small pixel assets. It should prove its value by benchmark before any Trace2D integration claim.

## P0 foundation — complete

P0 merged via PR #1 / squash `5626a11dbd9bc7dbe7459f5d088ffdd2bb11c6f2`.

Delivered:

- product and Agent authority contracts,
- preregistered benchmark methodology,
- reference-project/research register,
- machine-readable continuation lane,
- dependency-free Python 3.12+ package skeleton,
- compact deterministic `tracepixel doctor` command,
- GitHub-hosted CI on Python 3.12 and 3.13,
- public-repository safety rule excluding automatic untrusted PR execution on a future home self-hosted runner.

Owner CI run #1 passed on both Python 3.12 and 3.13 before merge.

## Current core lane

**P1 — Deterministic raster core / issue #2** is the exact active item.

```text
P1 deterministic raster core
 -> P2 Pixel IR + bounded operation vocabulary
 -> P3 staged authoring pipeline
 -> P4 deterministic pixel QA
 -> P5 provider-neutral Agent loop + complexity evidence
 -> P6 preview evidence + mobile gallery
 -> B0 matched benchmark
 -> P7 targeted repair/feedback loop
 -> B1 held-out benchmark
 -> P8 tiles/props breadth
 -> P9 Trace2D adapter experiment
```

P1 must prove exact canvas/palette/pixel mutation and deterministic authoritative pixel replay plus native PNG and nearest-neighbor preview fixtures **before any LLM/provider is introduced**.

Do not jump to Agent integration, Aseprite/MCP, VLM review or the home Windows runner while P1 remains open or has an active implementation PR.

## Preview direction

The owner should ultimately be able to inspect results from mobile without opening a desktop editor. Each explicit preview run should be able to publish:

```text
native PNG
+ enlarged nearest preview
+ stage contact sheet
+ deterministic QA JSON
+ agent-run evidence
+ static HTML gallery
```

The deterministic native/enlarged image pair begins in P1. Stage sheets and the mobile gallery are P6 after the underlying Pixel IR, staged pipeline, QA and Agent evidence contracts exist.

A home Windows PC may later act as an owner-triggered preview runner. It is not part of normal public-PR CI.

## Trace2D boundary

TracePixel does not modify Trace2D's runtime architecture. A future adapter may expose successful generation results as provider-neutral RGBA/metadata/manifests that can enter Trace2D's existing Sprite/Asset Intelligence preparation paths. Integration is deferred until the independent B0/B1 evidence warrants it.

## Continuation rule

The next `@GitHub TracePixel 다음 작업 진행해줘` must resolve live state first.

- If issue #2 has an implementation PR, continue/fix that PR until its exact-head checks are green and P1 is complete.
- If #2 is open with no implementation PR, begin P1 only.
- Only after P1 merges green should the lane advance to P2.
- Live GitHub state wins over stale prose.
