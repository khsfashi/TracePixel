# P11 — Generator-neutral quality-controller pivot

Status: **owner PIVOT confirmed 2026-08-18**. Active issue: #151.

This document is the architecture authority for the post-G8 pivot. It supersedes the assumption that complex production assets should primarily be generated through the staged/direct PixelProgram authoring path.

## 1. Product thesis after G8

TracePixel remains an independent project, but its product center changes from **own every pixel-generation decision** to **make heterogeneous generated raster candidates safe, inspectable, correctable and reviewable for game production**.

```text
replaceable generator / RAW / retained external candidate
 -> provider-neutral candidate boundary
 -> authoritative TracePixel Canvas
 -> deterministic QA / normalization
 -> bounded local repair when useful
 -> owner perceptual review
 -> exact replay / evidence / telemetry
 -> optional consumer handoff
```

TracePixel-direct is not deleted. It becomes:

- an optional generation backend/control,
- a small/simple-asset path where evidence supports it,
- a precision local-repair mechanism where exact pixel ownership is advantageous.

It is **not** privileged over RAW or external generators merely because TracePixel owns it.

## 2. Evidence that selected the pivot

The architecture decision is evidence-backed, not a roadmap preference.

- B0: RAW and staged methods both passed frozen structural requirements, while RAW received materially stronger owner-blind perceptual ratings.
- B1: the corrected staged path generalized structurally and removed owner rejections but did not prove perceptual superiority over RAW; mean staged orchestration cost remained roughly 4.6–5.1x on token/call/wall-time dimensions.
- G8: retained TracePixel humanoids `32111680356` and `32118899233` are owner REJECT.
- matched RAW run `32121042059` is also not proven production quality, but is materially clearer on anatomy, equipment attachment, material separation and local pixel-form readability under broadly similar one-call runtime cost.

`docs/G8_DIRECT_AUTHORING_POSTMORTEM.md` remains the frozen detailed authority for those runs.

The project therefore must not treat another humanoid schema/controller/retry as the default response to aesthetic failure.

## 3. Authority split

### Generator/backend authority

A generator may decide candidate pixels nondeterministically. Generator identity, model revision, prompt/settings and cost are provenance/evidence only.

A generator must not become canonical TracePixel state.

### TracePixel deterministic authority

Once one concrete candidate is accepted for inspection, TracePixel may own exact deterministic facts such as:

- RGBA8 canvas bytes,
- dimensions and alpha/background policy,
- exact palette membership/count where requested,
- connected components / isolated pixels,
- exact bounds/margins,
- tile/frame/manifest facts when the relevant contract exists,
- exact PixelProgram replay for deterministic repairs,
- before/after byte identities and changed-pixel accounting.

### Perceptual authority

The following remain perceptual/human unless a future experiment freezes a genuinely objective proxy for a narrower fact:

- recognizability,
- anatomy believability,
- pose readability,
- material readability,
- identity coherence,
- motion quality,
- pixel-cluster craft/style,
- overall aesthetic/product acceptance.

A deterministic green result never implies aesthetic acceptance.

## 4. Owner-operated experiment loop

The owner workflow must remain recoverable from repository state alone.

Normal continuation command:

```text
@GitHub TracePixel 다음 작업 진행해줘
```

A fresh agent follows live issue/PR state and `config/tracepixel.core-lane.json`.

For every provider-backed or externally generated scored/promotion experiment, freeze an experiment manifest before execution with at least:

- exact task/fixture identity,
- candidate backend identities,
- prompt/request information that must be equivalent across matched methods,
- provider/model/revision where relevant,
- provider-call/token/time/retry limits,
- deterministic checks,
- human review criteria,
- artifact/evidence retention paths,
- permitted repair/regeneration count.

Then run:

```text
frozen experiment
 -> owner-triggered bounded execution
 -> retain native PNG + enlarged preview + deterministic QA + cost evidence
 -> awaiting-owner-review
 -> explicit owner feedback
 -> accept/freeze OR bind rejection to exact artifact
 -> only the preregistered bounded repair/regeneration path
 -> review again or stop
```

### Mandatory stop at owner review

When state is `awaiting-owner-review`, autonomous continuation stops before another provider call.

The next agent must surface:

1. exact run/candidate identity,
2. native and enlarged preview artifacts,
3. deterministic QA status,
4. provider/token/iteration/wall-time evidence,
5. frozen human review criteria.

It must ask for owner judgment rather than infer approval.

### Natural-language owner feedback

The owner does not need to author JSON manually. A response such as:

```text
REJECT. silhouette는 괜찮은데 anatomy와 장비 부착이 별로고 재질도 안 읽힌다.
```

is valid input.

The agent converts it conservatively into existing P7 feedback/human-review contracts where applicable and binds it to the exact reviewed artifact/run digest. It must not invent stronger claims, missing regions, missing stages or acceptance criteria.

If the owner gives only an overall REJECT, all unspecified criteria remain `unresolved`, not automatically failed.

## 5. No autonomous aesthetic-score convergence loop

Do **not** implement:

```text
while aesthetic_score < threshold:
    regenerate()
```

Reasons:

- aesthetic judgment is not deterministic truth,
- evaluator optimization can diverge from owner preference,
- current TracePixel evidence already shows high orchestration cost,
- repeated generation can hide failures and destroy useful negative evidence.

A VLM may later be approved as bounded secondary evidence under G4, but it cannot silently become the final correctness/acceptance oracle.

Cheap deterministic QA/normalization may run repeatedly without provider calls when the operation is exact and bounded.

## 6. Reuse before invention

P11 must reuse existing seams before adding new ones:

- P1 Canvas/RGBA authority,
- P2 PixelProgram/exact replay,
- P4 deterministic QA,
- P7 feedback localization / minimal repair / human-feedback contracts,
- P6/P8 review-package patterns,
- existing complexity/telemetry evidence.

Do not create a second feedback authority, raster engine, animation engine, skeleton/IK/physics subsystem or generator scheduler merely for P11.

External projects such as PerfectPixel and sprite-gen are comparison/interop precedents. Do not clone their product stacks automatically. Trace2D already demonstrates the preferred separation: provider/generator formats are inputs while canonical asset authority remains local.

## 7. Fixed P11 child lane

```text
P11-X0 pivot authority + generator-neutral candidate contract
 -> P11-X1 owner experiment / review protocol
 -> P11-X2 deterministic candidate QA + normalization seam
 -> P11-X3 bounded local-repair / feedback binding
 -> P11-B0 128x128 static north-star benchmark freeze
 -> P11-B1 owner-triggered static benchmark + review package
 -> P11-P0 pivot postmortem / next-scope decision
```

### P11-X0

Contract-only. Freeze the minimum candidate envelope and authority boundary. No provider call.

### P11-X1

Make the owner-run/review state machine executable/recoverable. Reuse existing human-feedback authority rather than adding subjective score truth. No provider call is required merely to build the protocol.

### P11-X2

Prove generator-neutral candidates can pass through the same deterministic QA/normalization seam with exact evidence. Add only objective checks justified by target workloads.

### P11-X3

Prove owner feedback can drive bounded local repair while preserving unaffected pixels where required. Full regeneration is a separate explicit action and budget.

### P11-B0

Freeze the first production-facing north star: **128x128 static game art**. The benchmark must honestly compare only candidate families that can be matched under pinned conditions. Candidate families may include RAW/image generation, image generation plus deterministic pixel postprocess, TracePixel-direct as a control, and external generation plus TracePixel QA/repair.

### P11-B1

Run the frozen benchmark with retained unsuccessful attempts and explicit owner review. Human-visible quality and cost remain separate result layers.

### P11-P0

Freeze the result and ask the owner whether evidence supports any of:

- keep expanding generator-neutral static production,
- promote a 32x32 animation/sprite-sheet benchmark,
- keep direct authoring only as repair/control,
- retire additional parts of direct generation,
- consider Trace2D adapter work under G10.

None of those promotions is automatic.

## 8. Blocked scope during P11

Until P11-P0 plus an explicit owner decision:

- G9 **direct** animation/multi-frame generation remains blocked,
- unrestricted 128x128 product expansion outside the frozen P11 benchmark remains blocked,
- additional humanoid H0-H3-style schemas remain blocked,
- skeleton/IK/physics remains blocked,
- new PixelProgram operations remain evidence-gated,
- a new direct-generation architecture remains blocked,
- Trace2D integration remains blocked by G10.

## 9. Success criterion

P11 succeeds only if it demonstrates a useful capability that is not equivalent to "another generator can already draw the image."

Examples of meaningful evidence include:

- objective invalid candidates are rejected/repaired cheaply before perceptual review,
- owner-requested local changes preserve unaffected regions better or cheaper than regeneration,
- generator outputs converge to stable game-asset constraints with bounded cost,
- exact replay/evidence materially improves production debugging/review,
- generator-neutral comparison prevents provider/tool lock-in.

If P11 cannot show such value, the correct outcome may be to retain only the useful raster/QA/evidence components rather than expanding the project indefinitely.
