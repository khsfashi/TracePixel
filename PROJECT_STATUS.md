# Project Status

Last explanatory handoff update: **2026-08-18**

Live GitHub state and `config/tracepixel.core-lane.json` are operational authority.

## Current owner direction

TracePixel is now a **deterministic raster R&D lab**, not the standalone product owner for AI sprite generation, general pixel-art QA, showroom UI or asset management.

The human-facing production product is **Trace2D Asset Studio** (`khsfashi/Trace2D#318`). Trace2D already owns canonical Sprite assets/runtime/animation, SPP0-SPP5 processing/import/generation orchestration, WorkResult and Workspace review. TracePixel must not duplicate those surfaces merely to preserve project scope.

## What happened to P11

P11-X0 and P11-X1 are retained as useful research:

- generator-neutral candidate authority,
- owner-run / `awaiting-owner-review` state machine,
- exact artifact/run/digest binding,
- bounded provider/retry budgets,
- natural-language owner feedback without converting aesthetics into deterministic truth.

P11-X2/X3/B0/B1/P0 are **superseded** as active standalone-product work. Broad deterministic QA/normalization would overlap Trace2D SPP0-SPP5 and existing public tooling.

Issue #151 is superseded by #155.

## Active lane

**P12 — deterministic raster R&D and Trace2D handoff** / issue #155.

Current child:

```text
P12-R1 precision-edit matched benchmark freeze
```

Fixed P12 sequence:

```text
P12-R0 responsibility diff + unique-hypothesis freeze [complete]
 -> P12-R1 precision-edit matched benchmark freeze [active]
 -> P12-R2 owner-triggered matched run
 -> P12-P0 KEEP-AS-LAB / UPSTREAM / ARCHIVE decision
```

P12-R0 completed provider-free and feature-free. The frozen responsibility analysis is `docs/P12_R0_RESPONSIBILITY_DIFF.md`.

R0 found that region-local pixel mutation itself is not unique: Aseprite scripting/raw image APIs and ImageMagick region operations already provide mature primitives for bounded raster operations. The only candidate worth testing is the **Agent-facing bound-edit evidence contract**: exact source identity, explicit allowed/protected pixels, protected-pixel byte-equality proof, collateral-change measurement and deterministic replay/evidence.

P12-R1 must remain provider-free and feature-free until that matched experiment is completely preregistered.

## Frozen research thesis

The active hypothesis is:

> **For a frozen source sprite and a localized owner-requested edit, can an Agent using a TracePixel bounded-edit contract preserve every protected pixel byte-identically and materially reduce collateral pixel changes versus an unguarded RAW Agent raster-edit path (and an external image-edit path when honestly matchable), while still producing an owner-acceptable requested change at practical cost?**

Representative task shape:

```text
Shorten only the sword hilt.
Face, hair, body, palette and all pixels outside the allowed region must remain unchanged.
```

Matched evidence must keep these dimensions separate:

- requested visual change quality,
- exact protected-pixel violations,
- total/collateral changed pixels,
- provider calls/tokens/time,
- revisions,
- exact replay/evidence.

No composite score should hide a quality or collateral-damage loss.

## P12-R1 acceptance direction

Before any live/provider edit execution, R1 must freeze:

- realistic source sprite(s) and exact content digests,
- localized natural-language edit request(s),
- exact allowed region/mask and protected complement,
- owner-visible requested-change criteria,
- RAW Agent / honestly matchable external path / TracePixel bounded path,
- provider/model/tool versions and budgets where applicable,
- maximum calls/revisions and stop rules,
- retained artifact locations for success and failure,
- separate deterministic locality, owner-quality, cost and Agent-complexity metrics.

R1 does **not** execute the benchmark and does not add a new raster operation merely to make the benchmark easier.

## Preserved infrastructure

The repository retains:

- contiguous RGBA8 Canvas authority,
- PixelProgram validation/execution and exact replay,
- transactional mutation,
- deterministic QA primitives,
- P7 feedback localization/minimal repair/human-feedback contracts,
- P11-X1 owner review protocol,
- exact PNG/digest/diff evidence,
- provider/token/iteration/wall-time telemetry,
- immutable negative/scored benchmark evidence.

These are research tools, not proof that TracePixel needs to be a separate end-user product.

## Explicit non-goals

Do not build in TracePixel:

- Asset Studio/showroom UI,
- general asset library or project art-management product,
- broad sprite-sheet production orchestration,
- provider marketplace,
- duplicate alpha/palette/grid/frame processing already owned by Trace2D,
- new humanoid schema/skeleton/IK/physics,
- direct animation architecture without a new distinct hypothesis,
- autonomous aesthetic score-until-threshold loops.

## Trace2D relationship

Trace2D owns the production experience. TracePixel only upstreams a technique when a matched experiment shows a practical advantage for Trace2D Asset Studio or another explicit Trace2D workflow.

If no unique advantage is demonstrated, the correct P12 outcome is to preserve TracePixel as research evidence and stop/archive expansion.

## Owner workflow

Normal continuation remains:

```text
@GitHub TracePixel 다음 작업 진행해줘
```

A fresh Agent must resolve live state and continue only the active P12 child.

For any later provider-backed experiment:

```text
freeze matched experiment
 -> owner-triggered bounded run
 -> retain all outputs
 -> awaiting-owner-review
 -> owner natural-language judgment
 -> exact feedback binding
 -> only preregistered bounded continuation
```

When `awaiting-owner-review`, stop before another provider call. Reuse P11-X1/P7 rather than inventing a new feedback authority.

## Continuation rule

The next continuation must:

1. resolve live issue/PR/check state,
2. continue an existing P12 PR first,
3. otherwise begin only `current_child` from `config/tracepixel.core-lane.json`,
4. keep P12-R1 provider-free and feature-free until the entire matched experiment is frozen,
5. use `docs/P12_R0_RESPONSIBILITY_DIFF.md` as the scope boundary,
6. do not treat ordinary region editing/diff tooling as a unique TracePixel product claim,
7. preserve all prior negative evidence and never reopen G8 merely to chase a prettier result.
