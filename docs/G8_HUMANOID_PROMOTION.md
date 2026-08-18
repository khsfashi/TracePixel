# G8 Static-Humanoid Promotion Contract

G8 is the dedicated post-P10 implementation lane for the owner-approved humanoid/character destination. P10-C5 is frozen complete with an owner-accepted simple-creature result, so TracePixel may now define humanoid-specific static-authoring constraints. Real humanoid provider execution and raster generation remain blocked until G8-H4.

## Lane

```text
G8-H0 promotion/authority contract
 -> G8-H1 anatomy + proportion + identity profile schema/validation
 -> G8-H2 pose + equipment-anchor constraint schema/validation
 -> G8-H3 request binding + deterministic/perceptual evidence split
 -> G8-H4 retained static-humanoid authoring + complexity evidence
 -> G8-H5 owner review + promotion postmortem
```

G9 animation/multi-frame work remains blocked until the G8 static-humanoid evidence is frozen. P9 Trace2D integration still requires explicit G10 approval and is not implied by G8.

## G8-H0 purpose

H0 freezes the technical authority boundary before humanoid pixels are generated. It performs no provider calls and creates no humanoid raster evidence.

The required contracts are:

1. anatomy/proportion/identity profile,
2. static pose and equipment-anchor intent,
3. deterministic versus perceptual evidence responsibility,
4. complexity/cost accounting,
5. explicit preservation of the existing single-asset PixelProgram/Canvas raster authority.

## Anatomy / proportion / identity profile

The implementation target is a versioned, digest-pinned `tracepixel.humanoid-profile.v1` profile. It should reuse the provenance and immutable-profile seams already proven by P8/P10 instead of introducing a parallel character-description authority.

Required information categories include:

- character family/archetype or retained identity label,
- canonical body landmarks,
- bounded relative body-proportion ranges,
- symmetry and declared asymmetry,
- limb/joint relationships,
- head/face/hair identity-critical features appropriate to low resolution,
- silhouette-critical identity features,
- support/contact expectations,
- target-resolution and stylization tolerances,
- equipment/attachment anchor definitions,
- retained provenance/evidence references,
- explicit confidence and unknown fields.

Constraint severity remains typed:

- `required-range` for structured constraints that must validate,
- `hint` for authoring guidance that can be intentionally violated,
- `stylization-tolerance` for bounded low-resolution/stylized deviation.

The profile is research/evidence/authoring context only. It never becomes pixel authority and it does not replace PixelProgram or Canvas.

## Static pose / equipment-anchor contract

The implementation target is a versioned `tracepixel.humanoid-pose.v1` record digest-bound to the exact humanoid profile.

It may describe:

- named static pose and orientation intent,
- body-landmark/joint relationships,
- bounded articulation ranges,
- support/contact landmarks,
- coarse balance/contact intent,
- silhouette-facing expectations,
- equipment/attachment anchor identity,
- anchor occupancy and side intent,
- attachment overlap/occlusion intent.

H0 does not authorize a skeleton simulator, inverse-kinematics solver, physics engine, skeletal raster authority, or equipment-specific drawing engine. Structured pose and anchor data constrain authoring; resulting pixels still come only through the existing single-asset PixelProgram/Canvas path.

## Deterministic versus perceptual evidence

Deterministic code may prove exact facts such as:

- schema/version identity,
- digest binding,
- finite range validity,
- body-landmark reference integrity,
- equipment-anchor reference integrity,
- declared structured relation/range satisfaction where computable,
- support/contact declarations,
- declared orientation/attachment-side intent,
- existing raster and deterministic QA facts,
- retained provider/cost/provenance accounting.

The following remain perceptual/human unless a separately frozen measurable rule exists:

- whether the result reads as the intended humanoid/character,
- whether anatomy looks believable for the chosen stylization,
- whether the intended pose reads clearly,
- whether identity-critical features remain coherent,
- whether the silhouette reads clearly,
- whether equipment/attachments read correctly,
- whether visual style is coherent.

A VLM may be secondary evidence only under G4. It is not deterministic correctness truth. Final aesthetic acceptance remains human.

## Complexity / cost contract

G8 reuses existing single-asset complexity accounting. Retained humanoid attempts must preserve, when available:

- provider calls,
- input/output tokens,
- iterations/revisions,
- PixelProgram/tool/operation calls,
- pixel edits and changed pixels,
- deterministic QA findings,
- repair versus regeneration,
- wall time,
- cache/profile reuse,
- failure category.

**G8-H4 complexity is cumulative through the retained output that the owner actually accepts, not merely the first generated or first deterministic-QA-passing image.** Every retained H4 attempt before that accepted candidate remains part of the cost evidence. Each run keeps its own single-attempt raw record, while the candidate review artifact aggregates all prior retained H4 attempts plus the current attempt. When H5 accepts a candidate, H5 must freeze that exact cumulative record rather than recomputing only the final run.

The authoritative cost evidence is the raw usage itself: provider calls, input/output tokens, iterations/revisions, operation calls, pixel edits/changed pixels, repair/regeneration counts, profile/pose reuse and profile-research calls, and wall time. Currency/price conversion is derived and non-authoritative; it must not replace or outrank the raw usage metrics. H4 must compute absolute deltas, multipliers, and percentage changes against the owner-accepted P10-C4 simple-creature retained authoring baseline wherever the P10 baseline is non-zero. For zero baselines such as repair/regeneration, percentage change is mathematically undefined and the evidence must report the absolute delta instead of inventing a percentage.

Profile/reference preparation and equipment/attachment context preparation, if dynamic provider work is later introduced, must remain separately attributable. Humanoid structure must not hide work inside a second scheduler/planner or equipment renderer.

The B1 staged single-member cost warning remains unresolved and must continue to be reported rather than erased by humanoid promotion.

## G8-H0 prohibitions

Until H0 is green, and in practice until the preceding H1-H3 contracts are complete:

- no humanoid raster generation,
- no new humanoid provider execution,
- no animation/multi-frame implementation,
- no Trace2D adapter work,
- no new raster authority,
- no skeletal/physics/IK authoring authority,
- no equipment-specific second drawing engine,
- no VLM score promoted to correctness truth.

## Handoff to G8-H1

H1 should implement and test the smallest provider-neutral anatomy/proportion/identity profile schema and validator needed by this contract. It must remain independent of raster generation, keep constraint ranges finite and explicit, preserve provenance/digest identity, and fail closed on invalid landmark/anchor/profile references.
