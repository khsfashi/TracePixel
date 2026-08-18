# Project Status

Last explanatory handoff update: **2026-08-18**

Live GitHub state and `config/tracepixel.core-lane.json` are operational authority. This file is the current human-readable handoff, not a substitute for live PR/issue/check state.

## Current owner decision

**PIVOT confirmed 2026-08-18.**

G8 direct humanoid authoring did not earn promotion as the privileged production path.

Retained evidence:

- TracePixel humanoid run `32111680356` — technically valid, deterministic QA green, **owner REJECT**.
- TracePixel humanoid run `32118899233` — technically valid, deterministic QA green, **owner REJECT**.
- matched RAW run `32121042059` — one-shot comparison, no rerun authorized; still below proven product quality but materially clearer on anatomy/equipment/material separation than the TracePixel candidate.

Detailed frozen analysis: `docs/G8_DIRECT_AUTHORING_POSTMORTEM.md`.

Issue #119 is complete as a research/promotion lane with **owner REJECT + PIVOT** disposition. It must not be reopened merely to chase a better humanoid retry.

## Product direction after the pivot

TracePixel remains independent, but its product center is now generator-neutral quality/control rather than ownership of every generation step.

```text
replaceable generator / RAW / retained external candidate
 -> TracePixel candidate import / authoritative Canvas
 -> deterministic QA + normalization
 -> bounded local repair where useful
 -> owner perceptual review
 -> exact replay / evidence / telemetry
 -> game-ready output or retained rejection
```

The existing staged/PixelProgram direct path remains only as:

- an optional backend/control,
- a simple/small-asset path where evidence supports it,
- a precision local-repair path where exact changed-pixel authority creates value.

Do not add humanoid-specific schema/controller complexity just to make direct generation win.

Architecture authority: `docs/P11_GENERATOR_NEUTRAL_PIVOT.md`.

## Active lane

**P11 — Generator-neutral quality controller pivot and owner review loop** / issue #151.

Current child:

```text
P11-X0 pivot authority + generator-neutral candidate contract
```

Fixed P11 sequence:

```text
P11-X0 pivot authority + generator-neutral candidate contract
 -> P11-X1 owner experiment / review protocol
 -> P11-X2 deterministic candidate QA + normalization seam
 -> P11-X3 bounded local-repair / feedback binding
 -> P11-B0 128x128 static north-star benchmark freeze
 -> P11-B1 owner-triggered static benchmark + review package
 -> P11-P0 pivot postmortem / next-scope decision
```

P11-X0 is contract-only. It performs no provider generation merely to define the boundary.

## Owner workflow

Normal continuation remains:

```text
@GitHub TracePixel 다음 작업 진행해줘
```

A fresh agent must resolve live state and continue the one active child.

For any owner-triggered generation/promotion experiment, the repository must freeze the task/backends/budgets/retry limits/review criteria before provider execution.

Expected loop:

```text
frozen experiment
 -> owner-triggered bounded run
 -> native + enlarged preview + QA + cost evidence
 -> awaiting-owner-review
 -> owner ACCEPT / REJECT + natural-language feedback
 -> freeze result OR exact feedback binding
 -> only preregistered bounded repair/regeneration
 -> review again or stop
```

When state is `awaiting-owner-review`, the Agent must stop provider work and surface the exact result plus review criteria. The owner may respond naturally; JSON authoring is not required.

Do not use an autonomous aesthetic-score-until-threshold retry loop.

## What remains valuable and preserved

The pivot explicitly preserves:

- contiguous RGBA8 Canvas authority,
- deterministic PNG/export and exact raster evidence,
- PixelProgram validation/execution/canonical replay,
- deterministic QA and typed findings,
- P7 feedback localization / minimal repair / human-feedback contracts,
- changed-pixel and unaffected-region evidence,
- provider/token/iteration/wall-time telemetry,
- retained unsuccessful/negative benchmark artifacts,
- static/mobile review-package patterns.

These components may be useful regardless of which generator backend wins future quality benchmarks.

## Benchmark lessons carried forward

### B0

The frozen visible cohort showed structural success for RAW and staged methods but materially stronger human perceptual ratings for RAW. The staged completion semantics were also found to stop too early.

### B1

After the B0-driven repair, the staged method completed its intended stages and removed owner rejections, but did not establish perceptual superiority over the matched RAW baseline. Mean staged orchestration remained roughly 4.6–5.1x higher across major token/call/wall-time dimensions.

### G8

More humanoid structure/context did not produce owner-approved anatomy/equipment/material/pixel-cluster quality. A simpler matched RAW attempt was visually clearer on several core criteria. This is evidence against treating further H0-H3 schema expansion as the default fix.

## External-generator boundary

PerfectPixel, sprite-gen and similar public projects are references/comparison candidates, not automatic dependencies or code to clone.

Trace2D already provides a useful architectural precedent: generator/provider outputs are inputs to deterministic canonical import, not runtime authority.

P11 may later benchmark external candidate families honestly, but it must first freeze the generator-neutral boundary and owner-review protocol.

## Blocked scope

Until P11-P0 and a new explicit owner decision:

- G9 direct animation/multi-frame implementation remains blocked,
- unrestricted 128x128 product expansion outside the frozen P11 benchmark remains blocked,
- additional humanoid schema/skeleton/IK/physics remains blocked,
- new direct-generation architecture remains blocked,
- new PixelProgram operations remain evidence-gated,
- Trace2D integration remains blocked by G10.

A future 32x32 animation/sprite-sheet benchmark is a possible post-P11 owner promotion, not an automatic continuation.

## Owner decision gates

`docs/DECISION_GATES.md` remains the authority for decisions autonomous continuation must not silently cross.

Important unresolved/promotional gates now include:

- G4 VLM/perceptual judge as secondary evidence,
- G5 additional scored external-tool baselines where fair harnessing is possible,
- G9 animation/multi-frame promotion after post-pivot evidence,
- G10 Trace2D adapter experiment,
- G11 post-P11 production-scope decision.

If an owner decision already resolves the exact question, record it and do not ask again unless materially new evidence invalidates it.

## Historical phase record

P0 through P8, P10 and G8 implementation/evidence remain in repository history, issues, contracts and committed evidence directories. Do not rewrite or rerun frozen cohorts to fit the post-pivot narrative.

The most important immutable references are:

- `docs/B0_POSTMORTEM.md`,
- B1 retained postmortem/evidence,
- P8/P10 retained production/creature evidence,
- `docs/G8_DIRECT_AUTHORING_POSTMORTEM.md`,
- issue #119 final owner decision comment.

## Continuation rule

The next `@GitHub TracePixel 다음 작업 진행해줘` must:

1. resolve live issue/PR/check state,
2. continue an active P11 implementation PR first if one exists,
3. otherwise begin only `current_child` from `config/tracepixel.core-lane.json`,
4. stop before provider execution when the active child is contract/protocol-only,
5. stop at `awaiting-owner-review` and surface review artifacts instead of launching another provider call,
6. preserve rejected/failed evidence,
7. never silently reopen G8 direct-generation expansion.
