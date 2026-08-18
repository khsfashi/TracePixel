# G8-H5 owner-reject failure analysis

## Frozen verdict

Owner review for retained run `32111680356` is **REJECT**.

The candidate is retained as technically valid negative product-quality evidence. Its native PNG and raw/cumulative complexity evidence are immutable evidence inputs for this analysis. Deterministic QA green is not humanoid quality success, and this rejection does not advance G9 animation or Trace2D integration.

## Trace: H1/H2 -> provider -> PixelProgram -> raster

### H1 profile content

The retained H1 profile provides a valid biped structure, head/hand/foot landmarks, a broad head/body ratio, generic head-treatment and silhouette identity requirements, hand equipment anchors, and low-resolution exaggeration tolerance.

Evidence gap: the fixture does **not** name a concrete identity-bearing visual feature such as a specific hair/helmet/head-silhouette shape, and it carries no material-readability requirement. The profile contract is structurally sufficient to carry identity features; the retained fixture instance was not specific enough to make identity visually testable.

### H2 pose/equipment content

The retained H2 pose explicitly supplies:
- `three-quarter-right` facing,
- grounded paired foot contacts,
- head/torso/pelvis grouping,
- distinguishable hands/supports as silhouette intent,
- right-hand spear occupancy with `in-front` overlap/occlusion,
- left-hand-clear intent.

Therefore the provider did receive meaningful pose/equipment information. Arm/leg separation remained a coarse hint rather than a concrete fixture instruction, but three-quarter facing and spear attachment were not absent.

### Provider context

`evidence.g8_h4.retained_authoring._constraint_context()` projected the H1 identity/proportion/anchor fields and H2 pose/equipment fields into `BOUND_HUMANOID_CONTEXT`. The authoring instruction repeated three-quarter-right pose, readable hands/feet, right-hand spear attachment, free left hand, strong silhouette and coarse anatomy.

The successful technical attempt used one provider call (`18,943` input / `3,548` output tokens) and emitted exactly one `pixel_program` containing one `set_pixels` operation with 268 pixel edits.

The retained provider transcript contains no semantic anatomy/pose plan. We therefore cannot claim knowledge of the provider's hidden planning. We **can** conclude that supplied three-quarter/equipment constraints were under-realized by the emitted PixelProgram/final raster because the owner rejected the image and the retained raster does not reliably communicate those requested perceptual properties.

### PixelProgram -> final raster

PixelProgram v1 intentionally exposes only `set_pixels`, but the frozen Pixel IR states that `set_pixels` can express any finite RGBA raster. The retained proposal successfully placed 268 arbitrary RGBA pixels on the 32x32 canvas. There is no evidence that operation-vocabulary expressivity prevented a better humanoid.

## Five failure hypotheses

| # | Hypothesis | Evidence result | Action |
|---|---|---|---|
| 1 | Profile/pose information itself was insufficient | **Partial / evidenced.** Identity was generic and materials were absent; pose/equipment high-level intent was present. | Do not extend schema. Add concrete fixture-level identity/material direction through the existing provider-instruction seam. |
| 2 | Information existed but provider did not use it in the PixelProgram plan | **Evidenced at emitted-output level.** Three-quarter/right-hand-spear constraints were in provider context but were not reliably readable in the final result. Internal hidden planning cannot be asserted. | Distill the existing H1/H2 constraints into a shorter, concrete raster-facing brief instead of adding authority. |
| 3 | PixelProgram vocabulary could not express the needed form | **Not evidenced.** `set_pixels` is raster-complete for finite RGBA output. | No PixelProgram/schema expansion. |
| 4 | Iterative QA did not detect perceptual failure | **Evidenced.** H4 QA checks only structural/color/connectivity findings; successful attempt had `visual_observation_calls=0` and stopped immediately when deterministic findings became empty. | Keep deterministic QA for correctness, but make H5 explicit owner visual review mandatory; deterministic green cannot promote. |
| 5 | Repair loop optimized deterministic findings rather than anatomy/pose/identity | **Evidenced.** Failed run `32111453098` used 4 provider calls / 3 repairs / 0 visual observations while findings were only connectivity and palette-limit failures. | Retry is one-shot: max 1 provider call, 0 provider repair calls. Retain any failure instead of buying quality with retries. |

## Minimal retry fix

No H0-H3 schema or contract changes are authorized.

The retry:
- reuses the exact retained H1 profile, H2 pose and H3 request/evidence policy,
- changes only the provider-facing fixture brief,
- uses one provider call maximum,
- replaces the verbose generic authoring instruction with a compact H1/H2-derived raster brief,
- makes limb negative-space readability, hand-to-spear contact, concrete cloth/leather/metal reads, and an asymmetric head-silhouette identity feature explicit,
- performs no provider repair call,
- preserves PixelProgram/Canvas as the sole raster authority,
- adds no skeleton, IK, physics, equipment raster authority or VLM correctness authority.

The previous technically successful single attempt (`32111680356`) is the cost ceiling: provider calls must be `<= 1`, and measured input/output token totals must not exceed `18,943 / 3,548` for the retry to be eligible for H5 owner review.

## H5 acceptance gate

A retry cannot be promoted by deterministic QA. It reaches only `awaiting-owner-review` when deterministic QA and the cost guard pass.

Owner acceptance requires explicit approval of **all seven**:
1. anatomy,
2. pose readability,
3. silhouette,
4. equipment attachment,
5. material readability,
6. identity,
7. pixel-cluster quality.

Any missing or rejected criterion keeps G8 unpromoted.
