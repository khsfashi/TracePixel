# G8 direct-authoring postmortem and matched RAW baseline

Status: **G8-H5 owner REJECT; architecture decision pending matched RAW evidence.**

This document freezes the owner review of retained runs `32111680356` and `32118899233` and preregisters the smallest comparison needed to decide whether TracePixel's humanoid direct-authoring lane has product value. It does not authorize another G8 provider retry, another humanoid schema, a new PixelProgram operation, animation, or Trace2D integration.

## Frozen owner verdict

Both retained runs are technically valid evidence and product-quality failures. Their original GitHub Actions artifacts, native PNGs, enlarged previews, provider proposals, telemetry, QA and complexity evidence remain immutable negative evidence and must not be replaced by a later preferred image.

- `32111680356` / artifact `9315292791` / native PNG SHA-256 `35af63e33ea7d319a92aacbede1e641a4a1ca6aac7f428277e32bc0fb9e23d82` — **REJECT**.
- `32118899233` / artifact `9317806659` / native PNG SHA-256 `0ba697dd345272761428a98c4a26398ff9db760fa2ee6305a0a5b94b045bf247` — **REJECT**.

Deterministic QA green is only structural correctness evidence. It is not anatomy, equipment, material, identity, cluster or aesthetic acceptance. G9 animation and Trace2D integration remain blocked.

## Attempt-to-attempt postmortem

### Human-visible quality

| Criterion | `32111680356` | `32118899233` | Evidence-backed conclusion |
| --- | --- | --- | --- |
| Anatomy | REJECT. A readable biped exists, but head/torso/limb construction is boxy and weakly articulated. | REJECT. The pose is more active, but torso, arms and legs merge into ambiguous wedges/blobs and body landmarks do not read cleanly. | The minimal raster-facing brief did not solve anatomy. Do **not** infer another schema gap from this failure. |
| Pose readability | REJECT. Grounded stance exists, but the requested three-quarter-right guard reads mostly frontal/static. | PARTIAL IMPROVEMENT. Diagonal massing and asymmetry create more motion and rightward intent. | Brief wording improved motion, but pose improvement did not rescue anatomy or equipment semantics. |
| Silhouette | REJECT. Body and spear are visible, but the overall outline is generic and stiff. | PARTIAL IMPROVEMENT. Side-plume and diagonal pose make the outline more distinctive. | Silhouette is one of the few clear gains from the one-shot brief. |
| Equipment attachment | REJECT. A vertical spear is present, but the hand/grip relationship is weak and visually mechanical. | REJECT. Spearhead/shaft/hand do not form a clearly readable held object; structural connectivity is not semantic attachment readability. | Existing anchor context plus the stronger brief still failed perceptual attachment. |
| Material readability | REJECT. Color groups exist but cloth/leather/metal do not read strongly as distinct materials. | REJECT. Teal/brown/gray are present, but large brown/teal regions mix body/equipment roles and the metal read is tiny. | Naming materials in the raster-facing brief was insufficient. |
| Identity | REJECT. Generic adventurer head treatment. | PARTIAL IMPROVEMENT. The high side-plume changes the native silhouette, but reads more as a large appendage/hat shape than a resolved character identity. | Identity feature survived better than before, but remains below owner quality. |
| Pixel-cluster quality | REJECT. Broad forms exist, but many same-color one-pixel islands/highlights fragment the clusters. | REJECT. More colors and many tiny same-color islands remain; the promised coherent 2-4px cluster language is not consistently realized. | Minimal brief guidance did not solve cluster craft. |

Offline raster inspection is diagnostic only, not a new quality score: both images are one 4-connected visible component and stay within the palette ceiling; `32111680356` uses 10 visible RGBA colors across 268 visible pixels while `32118899233` uses 13 across 257. Those facts explain why deterministic QA can be green while owner quality is still poor.

### Cost

The second run did not buy owner acceptance. Compared with `32111680356`, `32118899233` used the same one provider call, one iteration and zero provider repairs while changing the raw cost only slightly:

| Metric | `32111680356` | `32118899233` | Delta |
| --- | ---: | ---: | ---: |
| Provider calls | 1 | 1 | 0 |
| Input tokens | 18,943 | 18,866 | -77 (-0.41%) |
| Output tokens | 3,548 | 3,471 | -77 (-2.17%) |
| Iterations/revisions | 1 / 1 | 1 / 1 | 0 |
| Pixel edits / changed pixels | 268 / 268 | 257 / 257 | -11 (-4.10%) |
| Provider repairs | 0 | 0 | 0 |
| Wall time | 97.756 s | 98.101 s | +0.344 s (+0.35%) |
| Final deterministic QA findings | 0 | 0 | 0 |

Therefore the remaining failure must not be explained away as missing H0-H3 schema by default. The experiment already provided the existing bound profile/pose/equipment context and then added a very concrete raster-facing brief; the owner-visible weaknesses persisted.

## Matched RAW baseline preregistration

The TracePixel side is the already-retained `32118899233` run. **Do not spend another provider call regenerating the TracePixel side.** The only new provider call authorized by this experiment is one RAW baseline call.

The RAW side must use:

- the same 32x32 humanoid fixture intent,
- the same Codex/ChatGPT provider boundary available on the trusted owner runner,
- model `gpt-5.6-sol`, reasoning effort `low`,
- at most one provider call, one iteration and zero provider repair calls,
- no TracePixel staged controller,
- no bound H1/H2 humanoid contract payload,
- no PixelProgram authoring operation,
- no result-chasing retry if quality is poor,
- the same deterministic QA policy applied **after** authoring for measurement only.

The RAW prompt carries equivalent task intent in plain raster-facing language: three-quarter-right grounded adventurer, readable limbs, right-hand short spear, left hand free, asymmetric high plume, teal cloth, brown leather, gray metal, top-left light, strong silhouette, coarse anatomy and coherent clusters. It returns sparse raw RGBA8 pixels directly. TracePixel Canvas/export/QA may be used only as a deterministic measurement/export harness after the provider response; they are not allowed to plan or repair the RAW image.

## Comparison fields

Human-visible quality and cost must remain separate. Do not collapse them into one synthetic score.

**Owner perceptual review:** anatomy, pose readability, silhouette, equipment attachment, material readability, identity, pixel-cluster quality.

**Raw cost/complexity:** provider calls, input/output tokens, iterations/revisions, wall time, pixel edits/changed pixels, deterministic QA findings/evaluations, provider repair count.

A deterministic QA failure is retained evidence, not permission to retry the RAW call.

## Architecture decision rule

After the RAW artifact exists:

- **RETIRE direct authoring** when RAW is owner-equal-or-better while materially cheaper and TracePixel supplies no demonstrated correction/reproducibility advantage worth the complexity.
- **PIVOT** when RAW quality is equal/better but TracePixel's independent deterministic pieces remain valuable. Preserve Canvas, PixelProgram exact replay, deterministic QA, local repair and evidence harness; move generation toward an external/raw generator feeding those pieces rather than continuing humanoid-specific direct planning.
- **KEEP direct authoring** only when TracePixel demonstrates a clear owner-visible quality advantage or a concrete correction/replay advantage that RAW does not provide at comparable cost. Structural QA green alone is insufficient.

Until that owner decision, G9 animation, 128x128 expansion, more humanoid schema, new generation architecture and Trace2D integration remain blocked.

## Existing external-generator overlap

Trace2D already has explicit interop work for public sprite pipelines instead of owning their generation runtimes. `docs/SPRITE_GENERATOR_INTEROP_SPP4.md` supports explicit `sprite-gen` component-row and `PerfectPixelV2` manifest adapters, lowers them into Trace2D's canonical sprite import path, and explicitly rejects taking ownership of those generators' generation/editor/runtime stacks.

TracePixel should follow the same separation if the matched baseline favors RAW/external generation: **external generator or raw author -> deterministic TracePixel import/Canvas -> deterministic QA -> bounded local repair where useful -> exact replay/evidence**. This is an architecture option only in G8-H5; do not clone, integrate or reimplement sprite-gen, PerfectPixel, or another external generator during this decision.

## Next owner decision point

Review the one retained RAW native PNG and 8x preview beside `32118899233`, mark the seven perceptual criteria for each, then inspect raw cost metrics separately. That review selects **KEEP / PIVOT / RETIRE**. No later lane advances before the decision is recorded.
