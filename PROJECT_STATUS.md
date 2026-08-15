# Project Status

Last explanatory handoff update: **2026-08-15**

This file is context. Live GitHub state and `config/tracepixel.core-lane.json` are operational authority.

## Product rule

> Humans define intent and judge the result. AI owns the iteration in between.

> Deterministic where possible. Multimodal where necessary. Human judgment at the end.

TracePixel is an independent research/production-tool project for agent-authored, deterministic small pixel assets. It should prove its value by benchmark before any Trace2D integration claim.

## Current core lane

Bootstrap foundation is being established first:

```text
P0 repository/agent/benchmark foundation
 -> P1 deterministic raster core
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

The exact sequence is also machine-readable in `config/tracepixel.core-lane.json`.

## P0 acceptance

P0 is complete when main contains:

- product/agent contracts,
- preregistered benchmark methodology,
- external reference register,
- minimal installable Python package,
- deterministic smoke/doctor command,
- portable GitHub-hosted CI,
- no provider key, GPU or self-hosted runner requirement.

After P0 merges green, the exact next item is **P1 deterministic raster core**. P1 should prove exact canvas/palette/pixel mutation and deterministic native PNG + nearest-neighbor preview fixtures before any LLM is introduced.

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

A home Windows PC may later act as an owner-triggered preview runner. It is not part of normal public-PR CI.

## Trace2D boundary

TracePixel does not modify Trace2D's runtime architecture. A future adapter may expose successful generation results as provider-neutral RGBA/metadata/manifests that can enter Trace2D's existing Sprite/Asset Intelligence preparation paths. Integration is deferred until the independent B0/B1 evidence warrants it.
