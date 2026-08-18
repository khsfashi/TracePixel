# P10 Simple-Creature Promotion Contract

P10 is the dedicated post-P8 implementation lane for the owner-approved G7 simple-creature/animal destination. P8-B6 is frozen complete; P10 may now define creature-specific constraints, but creature raster generation remains blocked until the contract children preceding it are green.

## Lane

```text
P10-C0 promotion contract
 -> P10-C1 morphology/species-profile schema + validation
 -> P10-C2 pose/constraint schema + validation
 -> P10-C3 request binding + deterministic/perceptual evidence split
 -> P10-C4 retained simple-creature authoring + complexity evidence
 -> P10-C5 owner review + promotion postmortem
```

Humanoids and animation remain later sequential G8/G9 promotions. P9 Trace2D integration still requires explicit G10 approval and is not implied by P10.

## P10-C0 purpose

C0 freezes the technical authority boundary before creature pixels are generated. It performs no provider calls and creates no creature raster evidence.

The required contracts are:

1. morphology/species profile,
2. pose/constraint intent,
3. deterministic versus perceptual evidence responsibility,
4. complexity/cost accounting.

## Morphology / species-profile contract

The implementation target is a versioned, digest-pinned `tracepixel.morphology-profile.v1` profile. It describes reusable coarse structure and authoring constraints, not pixels.

Required information categories:

- subject/species/form family identity,
- canonical landmark identifiers,
- relative segment/proportion ranges,
- symmetry/orientation expectations where applicable,
- articulation/joint relationships where applicable,
- silhouette-critical features,
- support/contact expectations,
- target-resolution stylization tolerances,
- retained provenance/evidence references,
- explicit confidence and unknown fields.

Constraint severity must remain typed rather than pretending realistic anatomy is universal aesthetic truth:

- `required-range` for constraints that must be validated,
- `hint` for authoring guidance that may be intentionally violated,
- `stylization-tolerance` for bounded low-resolution/stylized deviation.

Profiles are immutable inputs once digest-bound into a request. A materially improved profile creates a new version/digest; it does not silently mutate an old retained request.

The morphology profile is research/evidence/authoring context only. It never becomes raster authority, and it does not replace PixelProgram or Canvas.

## Pose / constraint contract

The implementation target is a versioned creature-pose constraint record bound to a morphology profile digest.

It may describe:

- named pose/orientation intent,
- landmark or joint relationships,
- bounded articulation ranges,
- required support/contact landmarks,
- coarse support/contact plausibility,
- silhouette-facing expectations,
- optional center-of-support hints where objectively meaningful,
- explicit required/hint/stylization constraint modes.

P10 does not add a physics engine, skeletal raster authority, inverse-kinematics solver, or full-body simulation. Pose constraints guide and validate authoring; resulting pixels still come only through the existing single-asset staged PixelProgram/Canvas path.

## Deterministic versus perceptual evidence

Deterministic code may prove exact facts such as:

- schema/version identity,
- digest binding,
- finite range validity,
- declared landmark identity/reference integrity,
- required relation/range satisfaction when computable from retained structured data,
- support/contact declarations,
- canvas/palette/QA facts already covered by existing TracePixel contracts,
- retained provider/cost/provenance accounting.

The following remain perceptual/human unless a separately frozen measurable rule is introduced:

- whether the creature is recognizable as the intended species/form,
- whether the silhouette reads clearly,
- whether anatomy looks believable for the chosen stylization,
- whether the pose communicates the intended action,
- whether visual identity and style are coherent.

A VLM may be secondary evidence only under the existing G4 authority; it is not deterministic correctness truth. Final aesthetic acceptance remains human.

## Complexity / cost contract

P10 reuses existing single-asset complexity accounting. Retained creature attempts must preserve, when available:

- provider calls,
- input/output tokens,
- iterations/revisions,
- PixelProgram/tool/operation calls,
- pixel edits and changed pixels,
- deterministic QA findings,
- repair/regeneration distinction,
- wall time,
- cache/profile reuse decisions,
- failure category.

Creature-specific structure must not hide provider or raster work in a second scheduler/planner authority. Research/profile construction cost, if later performed dynamically, must be separately attributable rather than silently folded into a synthetic quality/cost score.

The B1 staged single-member cost warning remains unresolved and must continue to be reported rather than erased by creature promotion.

## P10-C0 prohibitions

Until C0 is green:

- no creature raster generation,
- no new creature-specific provider execution,
- no humanoid implementation,
- no animation/multi-frame implementation,
- no Trace2D adapter work,
- no new raster authority,
- no physical-simulation engine,
- no VLM score promoted to correctness truth.

## Handoff to P10-C1

C1 should implement and test the smallest provider-neutral morphology/species-profile schema and validator needed by the contract above. It should remain independent of raster generation and reuse the P8 research-to-asset provenance/digest principles where they already fit.
