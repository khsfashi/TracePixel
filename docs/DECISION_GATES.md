# Owner Decision Gates

TracePixel is designed for autonomous continuation between explicit human decisions. This file defines decisions that an Agent must **not** silently make merely because implementation can continue.

When a gate is reached, stop the affected lane, summarize the evidence/trade-offs and ask the repository owner. Unrelated already-authorized work may continue only if it does not prejudge the decision.

## Decision principles

- Prefer evidence from committed fixtures/benchmarks over preference guesses.
- Separate reversible implementation detail from product-scope decisions.
- Do not use a benchmark result to silently broaden project scope.
- Record resolved owner decisions in the relevant issue/contract/status document.
- If an existing owner decision already resolves the exact question, do not ask again.

## G1 — Authoritative pixel representation

**Earliest lane:** P1-R0.

Default direction is a compact contiguous RGBA8 authority with palette/indexed workflows layered explicitly where useful.

Stop for owner review if a proposal would instead make palette indices the primary canonical pixel authority, introduce multiple competing canonical pixel stores, or materially complicate the simple RGBA8 baseline.

Decision evidence should include:

- storage/memory implications,
- deterministic replay implications,
- palette-edit/Agent compactness benefits,
- conversion/copy costs,
- compatibility with PNG/export and later Trace2D handoff.

## G2 — Image/PNG dependency

**Earliest lane:** P1-R2.

A tiny well-understood dependency may be justified, but do not add a large image stack merely for PNG export without comparison.

Present:

- standard-library/custom encoder complexity,
- candidate dependency maintenance/licensing/security footprint,
- determinism of encoding configuration,
- decode/export needs expected in later phases.

## G3 — First real Agent provider/model

**Earliest lane:** P5-A5.

Recorded/fake providers remain CI authority. Before any paid/network real-provider smoke becomes the reference run, ask the owner which provider/model/cost envelope to pin.

Record:

- provider/model/revision,
- settings,
- budget,
- whether vision input is used,
- expected API cost boundary.

## G4 — VLM/perceptual judge

**Earliest lane:** after deterministic QA exists; normally P5/P6 or B0 freeze.

Do not silently make a VLM score a correctness gate.

Owner decides whether a pinned VLM is used as secondary evidence and where. Final aesthetic approval remains human for product claims.

## G5 — Aseprite/MCP scored baseline

**Earliest lane:** B0 baseline freeze.

Reference study is allowed earlier. Inclusion as a scored competitor requires owner approval after confirming:

- implementation/version to pin,
- license/tool availability,
- fair matched prompt/model/budget,
- automation reliability.

If fair harnessing is not possible, keep it qualitative rather than manufacturing a score.

## G6 — Home Windows self-hosted preview runner

**Earliest lane:** P6-V6.

Never connect public pull-request events directly to the owner machine.

Before enabling the runner, present:

- trigger policy (owner/manual only),
- runner labels,
- secret exposure policy,
- concurrency/resource policy with other local GPU workloads,
- artifact upload/retention behavior.

## G7 — Simple-creature promotion

**Earliest lane:** P8-B4.

P8-B4 may begin when B1/P8 evidence supports wider semantic shapes, but creature identity introduces materially new morphology, perception and consistency requirements.

**Owner decision recorded 2026-08-17:** simple creatures/animals are an approved long-term product destination. Do not ask again whether creature scope is desired. Before implementation crosses this gate, define and test the morphology/species-profile, pose/constraint and perceptual evidence contracts; the approval does not authorize silently inventing those technical contracts.

Preferred direction is constraint-driven morphology/anatomy rather than full physical simulation, with realistic structure treated as ranges/hints where stylization requires deviation.

## G8 — Humanoid scope promotion

**Earliest lane:** P8-B5.

Humanoids add anatomy, pose, identity and stronger perceptual constraints.

**Owner decision recorded 2026-08-17:** humanoid/character authoring is an approved long-term product destination. Do not ask again whether humanoids belong in scope. Before implementation crosses this gate, present/commit the anatomy/proportion, pose, identity, equipment-anchor, QA/perceptual and complexity contracts so the promotion remains evidence-backed rather than roadmap creep.

The project still targets game-asset/sprite production rather than unconstrained general illustration.

## G9 — Animation / multi-frame promotion

**Earliest lane:** P8-B6.

Multi-frame consistency introduces temporal identity/motion constraints and may require new IR/QA/benchmark contracts.

**Owner decision recorded 2026-08-17:** animation, multi-frame sprites and sprite-sheet output are approved long-term destinations. Do not ask again whether animation/sprite sheets are wanted. Before implementation crosses this gate, define frame/rig/identity/motion authority, contact/root/pivot stability, deterministic frame ordering/sheet packing, complexity budgets and relevant animation baselines.

The preferred path reuses per-frame single-asset authority and adds explicit temporal consistency rather than creating a separate unbounded animation drawing engine.

## G10 — Trace2D adapter experiment

**Earliest lane:** P9-T0.

Always explicit even if B1/P8 evidence is positive.

The decision is not "is TracePixel good?" but "does a thin adapter measurably improve Trace2D's existing Sprite/Asset workflow without contaminating Trace2D runtime authority?"

Required evidence before asking:

- immutable B0/B1 results,
- representative successful production-breadth evidence,
- proposed provider-neutral RGBA/metadata/manifest seam,
- expected integration benchmark,
- confirmation that no Python/LLM/provider dependency enters Trace2D runtime/canonical asset state.

## Resolved-decision recording

When the owner resolves a gate:

1. record the decision and rationale in the active issue/contract,
2. update `PROJECT_STATUS.md` if it affects future continuation,
3. update `config/tracepixel.core-lane.json` only when execution order/current child changes,
4. do not ask the same question again unless new evidence materially invalidates the recorded decision.
