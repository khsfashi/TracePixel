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

## Current core lane

**P1 — Deterministic raster core / issue #2** is the exact active item.

Exact current child:

```text
P1-R0 raster authority contract
 -> P1-R1 canvas + transactional mutation
 -> P1-R2 deterministic export
 -> P1-R3 replay fixture + first visible preview
 -> P1-R4 memory/performance evidence
```

The next implementation must begin with **P1-R0** unless live GitHub state shows an already-active P1 implementation PR.

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
- If #2 is open with no implementation PR, begin **P1-R0 only**.
- Advance through `P1-R0 -> R1 -> R2 -> R3 -> R4` in order unless an explicit owner decision changes the contract.
- Stop at unresolved owner gates rather than guessing.
- Only after all P1 children merge green should the lane advance to P2-IR0.
- Live GitHub state wins over stale prose.
