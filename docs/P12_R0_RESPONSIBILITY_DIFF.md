# P12-R0 Responsibility Diff and Unique-Hypothesis Freeze

Status: **complete / provider-free / feature-free**  
Date: **2026-08-18**  
Parent: **#155**

## Purpose

P12 exists to keep TracePixel only where it can answer a narrow falsifiable raster-research question that is not already owned by Trace2D or ordinary mature raster tooling.

R0 intentionally adds **no raster feature, provider integration, retry, schema expansion, UI, generator, or animation work**. It freezes the responsibility boundary and the first hypothesis that may proceed to a matched experiment.

## Sources checked

### Trace2D authority

- Trace2D #59 — Sprite pipeline, including SPP0-SPP5 deterministic processing/QA, extraction, repair, import, interoperability and provider-neutral generation orchestration: <https://github.com/khsfashi/Trace2D/issues/59>
- Trace2D #178 — transactional semantic Sprite resource mutation/validation: <https://github.com/khsfashi/Trace2D/issues/178>
- Trace2D #318 — Asset Studio product owner for production requests, candidate review/showroom, asset library and TracePixel evidence-gated upstreaming: <https://github.com/khsfashi/Trace2D/issues/318>

### Current external raster/pixel tooling relevant to the proposed hypothesis

Checked 2026-08-18.

- Aseprite scripting/API supports image cloning, raw image bytes, rectangular pixel iteration, per-pixel mutation and image equality. Its CLI can execute scripts in batch mode. These primitives are already sufficient to implement a local-region edit or independently verify unchanged pixels; therefore local pixel mutation itself is not a TracePixel-unique capability.
  - <https://www.aseprite.org/docs/scripting/>
  - <https://www.aseprite.org/api/image>
  - <https://www.aseprite.org/docs/cli/>
- ImageMagick supports `-region geometry`, constraining subsequent operations to a specified region. Therefore a rectangular operation boundary is also not a TracePixel-unique primitive.
  - <https://imagemagick.org/command-line-options/#region>

The comparison is intentionally about responsibility/capability, not a claim that these tools expose TracePixel's proposed Agent-facing evidence contract.

## Responsibility diff

| Responsibility | Existing owner / evidence | Classification | P12 disposition |
|---|---|---|---|
| Canonical Sprite asset/runtime/animation authority | Trace2D Sprite/S1/SA/SR | already solved elsewhere | retire from TracePixel product scope |
| Generic alpha/background/frame extraction and segmentation | Trace2D SPP1 | already solved elsewhere | retire/avoid duplication |
| Generic pixel-grid, palette, pivot-jitter, identity/motion analysis and repair | Trace2D SPP2 | already solved elsewhere | retire/avoid duplication |
| Aseprite/generic sprite import and generator-manifest interoperability | Trace2D SPP3-SPP4 | already solved elsewhere | retire/avoid duplication |
| Provider-neutral generation orchestration | Trace2D SPP5 / Asset Studio | already solved elsewhere | retire/avoid duplication |
| Human-facing request/showroom/review/approval/asset-library product | Trace2D Workspace/WorkResult/#318 | already solved elsewhere | retire from TracePixel product scope |
| Transactional semantic Sprite metadata mutation | Trace2D #178 | already solved elsewhere | retire/avoid duplicate authoring model |
| Local rectangular/pixel mutation as a primitive | Aseprite API / ImageMagick region operations / TracePixel Canvas+PixelProgram | already solved elsewhere | not a unique research claim |
| Exact before/after raster byte comparison | straightforward with Aseprite raw bytes/equality or ordinary byte/pixel tooling; TracePixel already has digest/diff infrastructure | TracePixel-only as an integrated workflow is unproven | may be reused only inside a narrower experiment |
| Bind an Agent edit request to a frozen source digest plus explicit allowed/protected pixels, reject/measure out-of-bound changes, and retain exact changed-pixel evidence | no current Trace2D product contract identified; external tools provide primitives but not this repository's proposed bound Agent/evidence workflow | TracePixel-only but unproven | **measurably unique candidate** |
| Deterministic replay of the accepted bounded edit against the exact frozen source while preserving protected pixels byte-for-byte | TracePixel already has Canvas/PixelProgram/replay primitives; product usefulness is not proven | TracePixel-only but unproven | **measurably unique candidate** |
| Promotion of the bounded-edit technique into the production workflow | Trace2D #318 is the product owner | should upstream to Trace2D **only after evidence** | no automatic integration |
| Broad deterministic sprite QA/normalization product | duplicated by Trace2D SPP and mature tooling | should retire/archive | frozen historical research only |
| Direct complex humanoid generation, new humanoid schema, skeleton/IK/physics, animation architecture | G8 owner REJECT/PIVOT and P12 non-goals | should retire/archive | do not resume |

## What is *not* unique

P12 must not claim uniqueness for any of the following:

- editing only a rectangle,
- setting individual pixels,
- using a mask/selection,
- comparing two images,
- computing a diff count,
- generic palette/grid/alpha/frame cleanup,
- showing candidates to a user,
- transactionally editing canonical Trace2D Sprite metadata.

All are already available elsewhere or are ordinary implementation primitives.

## Frozen unique hypothesis

The first P12 hypothesis is:

> **For a frozen source sprite and a localized owner-requested edit, an Agent using a TracePixel bounded-edit contract can preserve every protected pixel byte-identically and materially reduce collateral pixel changes versus an unguarded RAW Agent raster-edit path (and an external image-edit path when honestly matchable), while still producing an owner-acceptable requested change at practical cost.**

This is deliberately stronger than "TracePixel can edit pixels." The candidate value is the combination of:

1. exact source identity,
2. explicit allowed/protected region identity,
3. bounded mutation authority,
4. exact protected-pixel violation evidence,
5. exact total/collateral changed-pixel evidence,
6. retained before/after/replay evidence,
7. separation of owner-visible requested-change quality from deterministic locality facts.

## Falsification rules

The hypothesis fails to earn promotion if any of these hold in the matched evidence:

- TracePixel changes protected pixels,
- the requested edit is visibly unacceptable to the owner even though locality metrics are good,
- RAW/external alternatives achieve the same zero-violation/locality result with comparable or lower complexity so the TracePixel contract has no practical workflow advantage,
- the TracePixel path requires materially higher provider/revision/Agent complexity without a compensating locality/replay benefit,
- the measured advantage depends on a benchmark-specific hard-coded answer rather than the frozen generic contract.

A failure is a valid P12 result and may lead to KEEP-AS-LAB or ARCHIVE rather than more architecture.

## P12-R1 gate

R1 is the next active child. It remains **provider-free and feature-free until the matched benchmark is fully frozen**.

R1 must preregister, before any provider/live edit execution:

- one or more realistic source sprite PNGs and their exact content digests,
- one localized natural-language edit request per source,
- exact allowed region/mask and protected complement,
- owner-visible requested-change review criteria,
- matched paths:
  - RAW Agent raster edit,
  - an external image-edit/generator path only where honestly comparable,
  - TracePixel bounded edit,
- identical source/request constraints wherever the tools permit,
- provider/model/tool versions and budgets when applicable,
- maximum calls/revisions and stop rules,
- retained-success and retained-failure artifact paths,
- separately reported metrics:
  - protected-pixel violations,
  - total changed pixels,
  - collateral changed pixels,
  - requested-change owner judgment,
  - provider calls/tokens/time,
  - Agent iterations/revisions,
  - replay/evidence properties.

Do **not** create a composite winner score.

R1 must not execute the matched run. Successful R1 advances to owner-triggered **P12-R2**.

## Promotion boundary

A successful matched result does not make TracePixel a new end-user product. It only permits proposing the smallest proven technique for Trace2D #318 or another explicit Trace2D workflow.

If the technique is not measurably useful, preserve the evidence and stop expanding TracePixel.
