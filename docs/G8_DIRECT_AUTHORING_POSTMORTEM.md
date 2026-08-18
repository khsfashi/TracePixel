# G8 direct-authoring postmortem and matched RAW baseline

Status: **G8-H5 owner REJECT; matched RAW baseline executed once; owner architecture decision = PIVOT (confirmed 2026-08-18).**

This document freezes the two rejected TracePixel humanoid attempts, the preregistered one-call RAW comparison, and the owner-confirmed architecture decision. It does not authorize another provider retry, another humanoid schema, a new PixelProgram operation, animation, unrestricted 128x128 expansion, a new direct-generation architecture, or Trace2D integration.

## Frozen owner verdict

Both TracePixel humanoid runs are technically valid retained evidence and product-quality failures. Their original native PNGs, previews, proposals, telemetry, QA and complexity evidence must not be replaced by a later preferred result.

- `32111680356` / artifact `9315292791` / native PNG SHA-256 `35af63e33ea7d319a92aacbede1e641a4a1ca6aac7f428277e32bc0fb9e23d82` — **owner REJECT**.
- `32118899233` / artifact `9317806659` / native PNG SHA-256 `0ba697dd345272761428a98c4a26398ff9db760fa2ee6305a0a5b94b045bf247` — **owner REJECT**.

Deterministic QA green is structural evidence only. It is not anatomy, equipment, material, identity, cluster or aesthetic acceptance.

## TracePixel attempt-to-attempt postmortem

| Criterion | `32111680356` | `32118899233` | Conclusion |
| --- | --- | --- | --- |
| Anatomy | REJECT: readable biped but boxy, weak articulation. | REJECT: more active pose but torso/limbs merge into ambiguous wedges. | Minimal raster-facing brief did not solve anatomy. Do **not** infer another schema gap. |
| Pose readability | REJECT: grounded but mostly frontal/static. | PARTIAL improvement: diagonal massing/asymmetry adds motion. | Motion improved without fixing anatomy/equipment semantics. |
| Silhouette | REJECT: generic/stiff. | PARTIAL improvement: plume and diagonal body are more distinctive. | Clear gain, still insufficient. |
| Equipment attachment | REJECT: spear exists but grip is weak. | REJECT: spearhead/shaft/hand do not read as a clearly held object. | Existing equipment-anchor context plus stronger brief was insufficient. |
| Material readability | REJECT: cloth/leather/metal weakly separated. | REJECT: color families exist but body/equipment roles blend. | Raster-facing material naming was insufficient. |
| Identity | REJECT: generic. | PARTIAL improvement: plume is distinctive but malformed/oversized. | Feature survived but not at owner quality. |
| Pixel-cluster quality | REJECT. | REJECT. | Coherent cluster guidance did not produce owner-quality craft. |

Diagnostic raster facts, not a perceptual score: `32111680356` has 268 visible pixels / 10 visible RGBA colors; `32118899233` has 257 / 13. Both end as one 4-connected visible component and deterministic QA reports zero final findings.

### TracePixel cost

| Metric | `32111680356` | `32118899233` |
| --- | ---: | ---: |
| Provider calls | 1 | 1 |
| Input tokens | 18,943 | 18,866 |
| Output tokens | 3,548 | 3,471 |
| Iterations / revisions | 1 / 1 | 1 / 1 |
| Pixel edits | 268 | 257 |
| Provider repairs | 0 | 0 |
| Wall time | 97.756 s | 98.101 s |
| Final deterministic QA findings | 0 | 0 |

The second TracePixel attempt therefore did not buy owner acceptance despite retaining the existing H1/H2 profile/pose/equipment context and adding an explicit raster-facing brief. Persistent failures are not evidence for more H0-H3 schema by default.

## RAW matched baseline — executed once

Run `32121042059` is the only authorized RAW call. Artifact `9318584657` has digest `sha256:e9b450a2b94046e12ed6c3c3f6d0ea55b7bd11b87e8064e5b633d016dd416808`.

The RAW side used the same 32x32 task intent, ChatGPT Codex boundary, `gpt-5.6-sol`, low reasoning, one provider call, one iteration and zero repair calls. It did **not** receive the TracePixel staged controller, bound humanoid contracts, or PixelProgram authoring surface. Canvas/export/QA were used only after provider output as deterministic measurement/export infrastructure.

The authoring call succeeded and final deterministic QA had zero findings. Native PNG SHA-256 is `0462260f8245cbe3048bb6ab46a3d1b5ba90e3c22e46276c4061cbac0c07c020`; preview SHA-256 is `eb2bcbafc501a77441c8e4ac82c9e4c498b1035cdfbeebaa475f12f5e12cd808`.

The workflow is intentionally retained as a failed run because the preregistered output-token ceiling was exceeded: 3,590 actual versus 3,548 ceiling, +42 tokens (+1.18%). This is **not** permission to rerun. The generated artifact, QA and telemetry remain valid evidence; the budget mismatch must remain visible.

### Human-visible comparison against `32118899233`

The following is reviewer observation to support the owner decision, not an owner PASS for RAW:

| Criterion | TracePixel `32118899233` | RAW `32121042059` | Observation |
| --- | --- | --- | --- |
| Anatomy | Ambiguous body wedges and merged limb structure. | Head, torso, two arms and two legs are substantially easier to parse. | **RAW clearer.** |
| Pose readability | More dynamic diagonal/rightward gesture. | Less dramatic but body separation and stance are easier to read. | **Mixed**: TracePixel more dynamic; RAW more legible. |
| Silhouette | Stronger exaggerated diagonal/plume silhouette. | Simpler but more immediately humanoid. | **Mixed**: distinctiveness vs legibility. |
| Equipment attachment | Spear semantics/grip are unclear. | Right arm/hand reaches a continuous shaft with a separate metal spearhead. | **RAW clearer.** |
| Material readability | Brown/teal masses mix roles. | Teal body cloth, brown leather/shaft and gray metal separate more clearly. | **RAW clearer.** |
| Identity | Large plume is distinctive but malformed. | Smaller plume is less dramatic but more coherent with the head/body. | **Mixed**, RAW more coherent. |
| Pixel-cluster quality | Owner rejected; fragmented/wedge-like local forms. | Still coarse and not owner-approved, but major visible forms read more cleanly at native intent. | **RAW visually cleaner**, still below proven product quality. |

This is enough to reject the hypothesis that the humanoid-specific staged/contracts path is required to obtain the clearer anatomy/equipment/material result. It is **not** enough to claim RAW itself is a finished product generator.

### Cost comparison — keep separate from quality

| Metric | TracePixel `32118899233` | RAW `32121042059` | RAW delta |
| --- | ---: | ---: | ---: |
| Provider calls | 1 | 1 | 0 |
| Input tokens | 18,866 | 17,533 | -1,333 (-7.07%) |
| Output tokens | 3,471 | 3,590 | +119 (+3.43%) |
| Iterations / revisions | 1 / 1 | 1 / 1 | 0 |
| Pixel edits | 257 | 277 | +20 (+7.78%) |
| Provider repairs | 0 | 0 | 0 |
| Wall time | 98.101 s | 99.965 s | +1.864 s (+1.90%) |
| Final deterministic QA findings | 0 | 0 | 0 |

Provider/runtime cost is therefore **mixed, not a decisive RAW cost win**. However, this does not erase the additional implementation/context/maintenance complexity already present in the humanoid staged/contracts path.

## Owner architecture decision: PIVOT

**Owner-confirmed disposition: PIVOT.**

Reasoning:

- **KEEP as the privileged complex-generation architecture is not supported**: TracePixel direct humanoid authoring did not demonstrate an owner-visible quality advantage. On anatomy, equipment attachment and material separation, the simpler RAW path is visibly clearer.
- **Project-wide RETIRE is too strong**: the comparison does not test whether deterministic candidate QA, normalization, exact replay, evidence or bounded local repair create durable production value independent of the generator.
- **PIVOT is supported**: preserve the parts whose value does not depend on the failed direct-generation strategy — Canvas, PixelProgram/exact replay, deterministic QA, bounded local repair, evidence/telemetry harness and import/export surfaces — while stopping further humanoid-specific staged generation/schema expansion.

The direct generator itself is not deleted. It is demoted to an optional backend/control and precision-repair mechanism where evidence supports it.

## Post-pivot architecture

The active direction is:

```text
external / RAW / optional TracePixel-direct candidate
 -> TracePixel deterministic candidate import / Canvas
 -> deterministic QA + normalization
 -> bounded local repair when useful
 -> explicit owner perceptual review
 -> exact replay / evidence / telemetry
```

Detailed authority and owner-operated continuation protocol live in `docs/P11_GENERATOR_NEUTRAL_PIVOT.md` and issue #151.

## Existing external-generator overlap

Trace2D already treats public sprite generators as interop sources rather than runtimes it must own. `docs/SPRITE_GENERATOR_INTEROP_SPP4.md` supports `sprite-gen` component-row and `PerfectPixelV2` manifest adapters into the canonical import path while explicitly avoiding ownership of their generation/editor/runtime stacks.

That separation is the relevant precedent for TracePixel. Do not clone, integrate or reimplement `sprite-gen`, PerfectPixel, or another external generator merely because PIVOT was selected. P11 first freezes a generator-neutral boundary and fair benchmark/review loop.

## Lane closure and blocks

G8 issue #119 is closed as completed research/promotion evidence with **owner REJECT + PIVOT** disposition.

Until P11-P0 and a new owner decision:

- G9 direct animation remains blocked,
- unrestricted 128x128 expansion outside the P11 north-star benchmark remains blocked,
- additional humanoid schema/skeleton/IK/physics remains blocked,
- new direct-generation architecture remains blocked,
- Trace2D integration remains blocked by G10.

The next active work is **P11-X0** under issue #151, not another G8 provider retry.
