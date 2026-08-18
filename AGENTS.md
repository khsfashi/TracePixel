# AGENTS.md

This repository is **ARCHIVED / research complete**.

## Authority order

When sources disagree, use this order:

1. live GitHub issue / pull request / required-check state,
2. `config/tracepixel.core-lane.json`,
3. `PROJECT_STATUS.md`,
4. `docs/ARCHIVE.md`,
5. historical stage contracts/docs/comments.

## Default continuation behavior

For `TracePixel next` / `@GitHub TracePixel 다음 작업 진행해줘`:

1. resolve live repository state,
2. read `config/tracepixel.core-lane.json`,
3. if it remains `status = archived`, **do not create a new implementation/research lane**,
4. report that TracePixel is research-complete,
5. direct product asset-production work to **Trace2D Asset Studio** (`khsfashi/Trace2D#318`).

Do not reinterpret a generic “next task” request as permission to unarchive the repository.

Only an explicit owner instruction containing a clear decision to **unarchive/reopen TracePixel** may establish new roadmap authority.

## Final product boundary

TracePixel is not the owner of:

- an Asset Studio or showroom,
- a project asset library,
- a provider marketplace,
- broad sprite/image generation orchestration,
- generic alpha/palette/grid/frame processing already covered by Trace2D SPP0-SPP5,
- canonical SpriteAsset/animation/runtime behavior,
- autonomous aesthetic approval,
- humanoid/skeleton/IK/physics generation architecture,
- multi-frame animation generation,
- batch/multi-asset production product scope.

The human-facing AI-operated asset-production product is **Trace2D Asset Studio**.

## Archived research that must remain intact

Preserve:

- P1 Canvas/RGBA authority,
- P2 PixelProgram/exact replay,
- P4 deterministic QA primitives,
- P7 feedback localization/minimal repair/human feedback,
- B0/B1 benchmark evidence,
- P10 simple-creature evidence,
- G8 humanoid negative evidence and matched RAW comparison,
- P11-X0 generator-neutral candidate identity,
- P11-X1 owner-review state machine,
- P12-R0 responsibility diff (`docs/P12_R0_RESPONSIBILITY_DIFF.md`),
- telemetry/evidence/preview machinery.

Do not mutate, overwrite, rerun or relabel frozen scored/negative evidence to obtain a preferred historical conclusion.

## P12 archive boundary

P12-R0 completed provider-free/feature-free in PR #157 and is historical evidence.

The owner archive decision stops the remaining proposed sequence:

```text
P12-R0 [complete / historical]
 -> P12-R1 [stopped]
 -> P12-R2 [not executed]
 -> P12-P0 [superseded by ARCHIVE]
```

No P12 precision-edit provider/model run is authorized by a generic continuation request.

No new PixelProgram operation, protected-region feature, QA family or benchmark implementation is justified merely because R0 identified a testable hypothesis.

## What the research concluded

The retained evidence did not establish a sufficient production advantage for staged/direct TracePixel authoring. Broad quality-controller expansion would also duplicate existing Trace2D/external-tool responsibilities.

Therefore:

- no new provider/model run is authorized,
- no new architecture should be invented to create a reason for TracePixel to exist as a product,
- deterministic QA green still never implies aesthetic/product PASS,
- historical P11 owner-review rules remain evidence/reference, not an active production loop.

## Allowed maintenance

Only when explicitly requested, archival maintenance may fix:

- security issues,
- broken repository accessibility,
- broken deterministic replay/tests caused by environment/toolchain drift where preserving reproducibility is the purpose,
- broken documentation links,
- corruption or accidental loss of retained evidence.

Such work must remain minimal and must not silently reopen feature development.

## Trace2D reuse rule

A future Trace2D workload may selectively reuse a historical TracePixel technique if that workload independently demonstrates the need.

Prefer upstreaming the smallest useful idea/code into Trace2D rather than reopening TracePixel as an active product.

TracePixel history remains research evidence, not automatic product authority.
