# Research-to-Asset and Structure-Aware Character Direction

TracePixel should not guess unfamiliar forms forever. When a requested asset introduces a form that is not already covered by a retained, versioned profile, the production path should be able to research that form, extract reusable structural constraints, freeze the result as an inspectable profile, and then author pixels from that profile.

This document records the owner-approved long-term direction. It does **not** make external research, anatomy, humanoids, animation, or a VLM part of P8-X0 execution.

## Research-to-Asset pipeline

Target flow:

```text
unfamiliar requested form
 -> bounded research/discovery
 -> source/evidence retention
 -> morphology/form feature extraction
 -> reusable versioned profile
 -> asset request references frozen profile digest
 -> existing single-asset authoring pipeline
 -> deterministic QA + perceptual review
```

The research result is evidence and authoring context, never raster authority. Generated pixels remain governed by the existing PixelProgram/Canvas contracts.

### P8-R0 requirements

P8-R0 should define the provider-neutral contract before enabling network research:

- explicit `known_profile` versus `research_required` resolution,
- bounded research budget and allowed source classes,
- retained source identities/citations and retrieval timestamps where applicable,
- a versioned morphology/form profile with a content digest,
- separation between observed facts, inferred constraints, and artistic conventions,
- no copyrighted source image copied into canonical generated assets merely because it was researched,
- later requests reference a frozen profile digest rather than silently re-researching/re-guessing the same form,
- profile invalidation/versioning when materially better evidence changes the structure,
- benchmark freezes pin any research/profile state used by scored methods.

## Morphology Profile direction

A future `tracepixel.morphology-profile.v1` should describe reusable coarse structure, not a universal ontology of every object. Candidate fields include:

- subject/form family,
- canonical landmarks,
- relative segment/proportion ranges,
- symmetry and orientation expectations,
- articulation/joint relationships where applicable,
- silhouette-critical features,
- support/contact expectations,
- allowed stylization tolerances by target resolution,
- provenance/evidence references,
- explicit confidence/unknown fields.

P8-X0 only allows immutable morphology-profile references in an AssetSet; it does not yet define or execute this schema.

## Anatomy Constraint Layer

For creatures and characters, prefer constraint-driven structure over full physical simulation.

Useful constraints include:

- body proportions and invariant limb/segment lengths,
- joint topology and bounded articulation ranges,
- pose plausibility,
- support/contact and coarse center-of-mass checks where meaningful,
- front/side/three-quarter identity consistency,
- per-frame skeleton/morphology continuity for animation.

Avoid treating one anatomical template as aesthetic truth. Chibi, stylized, fantasy and low-resolution sprites intentionally violate realistic proportions. Constraints should therefore be typed as required ranges, hints or stylization profiles rather than hard-coded photoreal anatomy.

## Owner-approved long-term promotions

The repository owner explicitly approved the long-term destination on 2026-08-17:

1. **G7 simple creatures / animals** — species- or morphology-aware structure profiles and pose constraints.
2. **G8 humanoids / characters** — anatomy, pose, identity and equipment-anchor constraints.
3. **G9 animation / multi-frame** — frame continuity, contact/root/pivot stability, motion-aware QA and sprite-sheet export.

This approval resolves the product-scope question. Implementation still proceeds in lane order and must define/test the new deterministic/perceptual/complexity contracts before each promotion is considered complete.

## Animation / sprite-sheet destination

Target flow:

```text
character morphology profile
 -> reusable rig/skeleton constraints
 -> named pose or motion intent
 -> frame sequence with invariant identity
 -> per-frame single-asset authoring/replay
 -> temporal consistency QA
 -> sprite-sheet packing + frame metadata
```

Important future checks:

- limb/segment length stability across frames,
- controlled root motion,
- support-foot/contact phase stability,
- bounded joint delta between adjacent frames,
- palette/outline/style continuity,
- deterministic frame ordering and sheet packing,
- per-frame failure isolation and retained evidence.

## Boundary with P8 AssetSet

AssetSet is the production container, not a new drawing engine. It may share digest-pinned style, palette or morphology profiles, but every member must continue to use the proven single-asset authoring path. Batch scale must not hide member-level cost, failure, QA or provenance.
