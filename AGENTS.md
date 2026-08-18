# AGENTS.md

This repository is designed to be continued by fresh AI agents without hidden chat context.

## Authority order

When sources disagree, use this order:

1. live GitHub issue / pull request / required-check state,
2. `config/tracepixel.core-lane.json`,
3. `PROJECT_STATUS.md`,
4. active-stage contracts/docs,
5. roadmap prose and older comments.

## Continuation rule

For `TracePixel next` / `다음 작업 진행해줘`:

1. resolve live repository state,
2. identify the one active core child,
3. continue an existing PR before opening new scope,
4. implement only what the active child authorizes,
5. keep contract/research-only children provider-free,
6. preserve frozen negative/scored evidence,
7. stop at owner-review states instead of silently approving or launching another provider run.

## Current product boundary — P12

TracePixel is a **deterministic raster R&D lab**. It is not the end-user product owner for AI sprite production.

The product owner for AI-operated sprite production, showroom/review and project asset-library workflow is **Trace2D Asset Studio** (`khsfashi/Trace2D#318`).

Do not build here merely because the capability sounds related to pixels.

Explicit non-goals for ordinary continuation:

- standalone Asset Studio/showroom UI,
- general asset library,
- provider marketplace,
- broad sprite-sheet production pipeline,
- duplicate generic alpha/palette/grid/frame processing already owned by Trace2D SPP0-SPP5,
- new humanoid schema/skeleton/IK/physics,
- direct animation architecture without a distinct new research hypothesis,
- autonomous aesthetic scoring/approval.

P11-X0/X1 remain useful frozen research. P11-X2/X3/B0/B1/P0 are superseded as active standalone-product work.

## Active research rule

P12 asks narrow falsifiable questions about Agent-controlled raster editing.

Current sequence:

```text
P12-R0 responsibility diff + unique-hypothesis freeze [complete]
 -> P12-R1 precision-edit matched benchmark freeze [active]
 -> P12-R2 owner-triggered matched run
 -> P12-P0 KEEP-AS-LAB / UPSTREAM / ARCHIVE decision
```

### P12-R0 — frozen scope boundary

`docs/P12_R0_RESPONSIBILITY_DIFF.md` is the authority for what R0 found.

R0 established that ordinary region-local pixel mutation is **not** a unique TracePixel capability. Aseprite/ImageMagick and ordinary raster tooling already provide region/pixel mutation and comparison primitives, while Trace2D already owns generic Sprite processing, production review and transactional Sprite metadata authoring.

Do not reopen those responsibilities in TracePixel.

### P12-R1 — active child

R1 must perform **zero provider/live edit calls and zero new raster feature implementation until the matched experiment is fully frozen**.

Freeze before execution:

- exact source sprite identity/content digest,
- localized natural-language edit request,
- exact allowed region/mask and protected complement,
- owner-visible requested-change review criteria,
- matched RAW Agent / honestly matchable external / TracePixel bounded paths,
- provider/model/tool versions and budgets when applicable,
- maximum calls/revisions and stop rules,
- retained success/failure artifact locations,
- separate quality, locality, cost, Agent-complexity and replay/evidence metrics.

R1 does not run the benchmark. When the preregistration is complete and checks are green, advance to owner-triggered P12-R2.

### Frozen unique hypothesis

The first candidate is **protected-region precision editing / collateral-damage control**:

> For a frozen source sprite and a localized owner-requested edit, an Agent using a TracePixel bounded-edit contract can preserve every protected pixel byte-identically and materially reduce collateral pixel changes versus an unguarded RAW Agent raster-edit path (and an external image-edit path when honestly matchable), while still producing an owner-acceptable requested change at practical cost.

Representative shape:

```text
Shorten only the sword hilt.
All pixels outside the allowed region must remain byte-identical.
```

The candidate value is the combined Agent-facing contract, not the primitive ability to edit a rectangle:

- exact source identity,
- explicit allowed/protected pixel identity,
- bounded mutation authority,
- exact protected-pixel violation evidence,
- exact total/collateral changed-pixel evidence,
- retained before/after/replay evidence,
- separation of owner-visible quality from deterministic locality facts.

Measure separately:

- requested-change visual quality,
- exact protected-pixel violations,
- total/collateral changed pixels,
- provider calls/tokens/time,
- revisions,
- replay/evidence properties.

Never hide trade-offs in one composite winner score.

## Deterministic versus perceptual authority

- Exact raster mutation and exact measurable facts may be deterministic.
- Dimensions, alpha, explicit palette membership, bounds, byte equality, changed-pixel sets and protected-region violations are deterministic facts when frozen that way.
- Readability, anatomy, identity, material perception, style, pixel-cluster craft and taste remain perceptual/human unless a narrower objective fact is separately defined.
- Deterministic QA green never means aesthetic PASS.
- A VLM may only be bounded advisory evidence under an explicit owner gate; it is not final truth.

## Owner-run / feedback protocol

Reuse the frozen P11-X1/P7 owner protocol for later provider-backed P12 experiments:

```text
frozen-experiment
 -> owner-triggered-run
 -> awaiting-owner-review
 -> accepted | repair-requested | rejected-stop
```

When `awaiting-owner-review`:

1. make no additional provider call,
2. surface exact run/candidate/digest identity,
3. surface native/enlarged artifacts,
4. report deterministic evidence separately from cost,
5. show frozen human review criteria,
6. accept natural-language owner feedback,
7. bind feedback to the exact reviewed artifact conservatively.

Unspecified criteria remain unresolved. Do not invent region hints or silently reinterpret owner REJECT as PASS.

Rejected results remain immutable evidence.

## Retry / repair discipline

Do not implement `while aesthetic_score < threshold: regenerate()`.

- Provider repair/regeneration only occurs inside a preregistered bounded experiment.
- Never increase budget after seeing a rejected result merely to chase approval.
- Prefer exact local repair only when the hypothesis explicitly tests it.
- Full regeneration is a separate budgeted action.

## Promotion rule

TracePixel code is promoted into Trace2D only if matched evidence shows a practical advantage for Trace2D Asset Studio or another explicit Trace2D workflow.

No automatic upstreaming because an implementation exists.

If P12 fails to show a unique advantage, `ARCHIVE/STOP` is a valid and preferred outcome over further architectural expansion.

## Preserved research infrastructure

Reuse before invention:

- P1 Canvas/RGBA authority,
- P2 PixelProgram/exact replay,
- P4 deterministic QA primitives,
- P7 feedback localization/minimal repair/human feedback,
- P11-X0 candidate identity,
- P11-X1 owner-review state machine,
- existing telemetry/evidence/preview machinery.

New PixelProgram operations or new abstractions require measured workload evidence and an active P12 need.

## Benchmark integrity

- Freeze task, alternatives, provider/model versions, budgets and review criteria before scored/provider runs.
- Preserve all unsuccessful attempts.
- Do not rerun until a preferred result appears.
- Report quality, collateral damage and cost separately.
- Never mutate historical B0/B1/G8 evidence to fit the current narrative.

## Performance and safety

Heavy generation/analysis/preview work is offline tooling work.

- Avoid unnecessary decoded-image copies and per-pixel Python object graphs.
- Prefer compact contiguous buffers.
- Reuse temporary capacities only where measurement justifies it.
- Portable CI remains provider-free and GitHub-hosted.
- Never expose an unrestricted owner self-hosted runner to automatic public PR execution.
- Paid/model calls are explicit owner-triggered experiments only.
