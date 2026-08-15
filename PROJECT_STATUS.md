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

## Roadmap hardening

The project keeps the original P1-P9 sequence, but each phase now has a fixed child lane in `docs/ROADMAP.md` and `config/tracepixel.core-lane.json`.

Cross-cutting additions:

- explicit child-lane acceptance/stop boundaries,
- pre-B0 engineering checkpoints,
- incremental preview milestones,
- explicit owner decision gates in `docs/DECISION_GATES.md`,
- scored B0/B1 freeze/postmortem rules that preserve unsuccessful runs.

The purpose is to let future `TracePixel next/continue` work proceed autonomously on reversible engineering details while stopping before product/scope decisions that require owner judgment.

## P1-R0 raster authority — complete

P1-R0 froze the baseline that later raster code must preserve:

- top-left origin, zero-based half-open integer coordinates,
- one contiguous row-major RGBA8 canonical pixel store,
- exact straight/unpremultiplied alpha bytes with transparent RGB preserved,
- palette/index data is derived or authoring metadata rather than competing pixel authority,
- 4096 per-axis safety ceiling / 64 MiB maximum authoritative RGBA allocation,
- explicit raster contract error categories,
- all-or-nothing ordered batch mutation semantics with deterministic last-write-wins duplicates,
- authoritative replay truth is dimensions plus exact RGBA bytes; PNG bytes are export evidence unless an encoder contract later proves byte identity.

Executable layout/bounds/color validation lives in `tracepixel.raster.CanvasSpec` and `docs/RASTER_AUTHORITY.md` is the written authority.

## P1-R1 canvas + transactional mutation — complete

PR #6 implements the frozen R0 authority without reopening G1:

- one owned contiguous `bytearray` backing store,
- deterministic transparent-black initial state,
- exact `get_pixel` and `set_pixel`,
- ordered `set_pixels` transactional batch mutation,
- full batch shape/coordinate/color validation before authoritative writes,
- invalid batches leave authoritative pixels unchanged,
- duplicate coordinates resolve by deterministic last-write-wins order,
- no PNG/image dependency, semantic drawing primitive, provider call or second canonical pixel store.

PR #6 passed GitHub-hosted CI on Python 3.12 and 3.13 before merge.

## P1-R2 deterministic export — complete after PR #7 merges green

PR #7 implements deterministic export without opening G2:

- exact native-size RGBA8 PNG export,
- integer nearest-neighbor enlarged preview with no interpolation or antialiasing,
- explicit `tracepixel.png-export.v1` metadata including source/output dimensions and SHA-256 evidence,
- controlled encoder identity `tracepixel.png.rgba8.store.v1`,
- fixed PNG filter 0 plus stored DEFLATE blocks so encoder-v1 byte output is deterministic and golden-tested,
- exact authoritative RGBA bytes remain the stronger semantic replay truth,
- public `Canvas.rgba_bytes()` provides an explicit owned snapshot while synchronous package export reads the source through a read-only zero-copy view,
- enlarged preview materializes one scaled row at a time rather than a second authoritative canvas,
- no Pillow/libpng wrapper, provider, GPU requirement or new semantic drawing operation.

The PR #7 implementation head `34964826ccfaafa8d0fcb42aad27a83f50ae5b81` passed GitHub-hosted CI run #13 on Python 3.12 and 3.13 before the child handoff was advanced. The final handoff head must also be green before merge.

## Current core lane

**P1 — Deterministic raster core / issue #2** remains the active phase.

Exact current child after PR #7 merges green:

```text
P1-R3 replay fixture + first visible preview
 -> P1-R4 memory/performance evidence
```

P1-R3 must commit at least one recognizable small non-humanoid fixture such as a potion, key, gem or simple sword/symbol and prove exact authoritative RGBA equality, stable structural metadata, native PNG output and enlarged nearest-neighbor preview. This is the first roadmap point where the owner should be able to inspect an actual generated TracePixel raster result.

P1 must prove exact canvas/pixel mutation and deterministic authoritative pixel replay plus native PNG and nearest-neighbor preview fixtures **before any LLM/provider is introduced**.

Do not jump to Agent integration, Aseprite/MCP, VLM review or the home Windows runner while P1 remains open or has an active implementation PR.

## Early engineering checkpoints

Before the scored B0 cohort:

```text
P1-R4 raster memory/copy evidence
P2-IR4 IR compactness/replay/invalidity evidence
P4-Q5 seeded deterministic QA coverage
P5-A5 non-scored Agent complexity pilot
```

These are architecture diagnostics, not held-out product claims. They may change later implementation before B0 is frozen.

## Preview direction

Human visibility is incremental:

```text
P1-R3 -> native PNG + enlarged nearest preview
P3-S7 -> stage-by-stage preview evidence
P4-Q5 -> preview + deterministic QA
P5-A5 -> first opt-in AI-authored raster preview
P6-V5 -> mobile static gallery/review flow
```

A home Windows PC may later act as an owner-triggered preview runner at P6-V6. It is not part of normal public-PR CI and requires explicit owner approval before connection.

## Owner decision gates

`docs/DECISION_GATES.md` is authoritative for questions autonomous continuation must not silently resolve.

Important future gates include:

- materially changing the canonical pixel representation,
- adding a substantial image/PNG dependency,
- choosing the first real provider/model,
- using a VLM as secondary perceptual evidence,
- including Aseprite/MCP as a scored baseline,
- connecting the home self-hosted runner,
- promoting humanoids or animation into scope,
- starting the Trace2D adapter experiment.

If an existing recorded owner decision already answers the exact gate, do not ask again unless materially new evidence invalidates it.

## Benchmark direction

B0 is development-visible architecture evidence, not a final marketing claim. One exact preregistration commit must freeze tasks, baselines, provider/model settings, budgets, scoring, retry/exclusion policy and retention rules before scoring.

B0 remains immutable after scoring. B1 begins only after B0-driven changes are implemented and uses held-out frozen variants.

## Trace2D boundary

TracePixel does not modify Trace2D's runtime architecture. A future adapter may expose successful generation results as provider-neutral RGBA/metadata/manifests that can enter Trace2D's existing Sprite/Asset Intelligence preparation paths.

P9 does not begin automatically from positive benchmark results: it additionally requires explicit owner approval and its own matched integration benchmark.

## Continuation rule

The next `@GitHub TracePixel 다음 작업 진행해줘` must resolve live state first.

- If issue #2 has an implementation PR, continue/fix that PR until its exact-head checks are green and the active P1 child is complete.
- If #2 is open with no implementation PR, begin the `current_child` from `config/tracepixel.core-lane.json` only.
- Advance through `P1-R0 -> R1 -> R2 -> R3 -> R4` in order unless an explicit owner decision changes the contract.
- Stop at unresolved owner gates rather than guessing.
- Only after all P1 children merge green should the lane advance to P2-IR0.
- Live GitHub state wins over stale prose.
