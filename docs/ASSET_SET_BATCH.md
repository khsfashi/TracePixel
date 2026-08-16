# AssetSet / Batch Authoring Plan

Status: planned future production-breadth capability.

TracePixel currently treats one constrained pixel asset as the primary authoring unit:

```text
ArtIntent
 -> StagePlan / PixelProgram
 -> Canvas
 -> deterministic QA
 -> preview/evidence
```

Production workflows also need a bounded way to request and review **multiple assets as one set** without replacing the proven single-asset pipeline or forcing every asset to regenerate when one member fails.

This capability is preregistered as **P8-X0 AssetSet / batch authoring foundation**, executed before the existing P8-B0 production-breadth children.

## Product goal

Support requests such as:

```text
RPG item set
 -> potion x3 variants
 -> sword x4 variants
 -> key x2 variants
 -> shield x3 variants
```

while preserving per-asset deterministic authority, QA, replay evidence, failure isolation and mobile review.

P8-X0 is **not** "launch N unconstrained model calls in parallel". The first contract should define the set and reuse the existing single-asset authoring path for each member. Provider concurrency is a separate bounded execution policy layered on top later.

## Proposed authority shape

```text
AssetSetIntent
  -> ordered AssetRequest[]
      -> existing single-asset pipeline
      -> per-asset authoritative raster + QA + evidence
  -> AssetSetManifest
  -> optional set-level consistency facts/policy
  -> batch gallery / review evidence
```

Each asset remains independently replayable and independently validatable. `AssetSet` metadata must not become a second raster authority.

## P8-X0 minimum contract

1. **Versioned AssetSet intent**
   - stable set ID,
   - bounded ordered asset IDs,
   - one validated ArtIntent-equivalent request per asset,
   - explicit variant/group relationships when requested,
   - closed maximum member count and total budget.

2. **Reuse, not duplication**
   - invoke the existing single-asset authoring/QA/preview path per member,
   - do not introduce a second Canvas, PixelProgram executor or deterministic QA implementation for batch mode.

3. **Per-asset isolation**
   - one member failure does not invalidate successful members unless an explicit all-or-nothing set policy requires it,
   - successful member evidence can be cached/reused,
   - retry/repair targets only failed or explicitly invalidated members.

4. **Deterministic set manifest**
   - canonical member order,
   - asset ID -> intent/result/evidence digests,
   - status and failure category per member,
   - exact source commit/provider settings where applicable,
   - no hidden replacement of one member by another.

5. **Set-level consistency layer**
   - keep objective checks deterministic when they are explicitly requested,
   - examples: shared dimensions, palette membership/budget, alpha policy, naming/slot completeness, requested variant counts,
   - style/identity/aesthetic consistency remains perceptual/human unless a later frozen measurable rule exists.

6. **Batch review surface**
   - gallery shows all members with per-asset PASS/FINDINGS/failure state,
   - failed members are visibly distinguishable from accepted cached members,
   - mobile review can inspect one member without losing set context.

## Execution and performance direction

The default implementation should favor bounded resource use over eager full-set residency.

For `N` assets:

- scheduling/bookkeeping: `O(N)`,
- per-asset raster/QA cost: existing single-asset cost,
- persistent evidence: proportional to emitted results,
- live Canvas memory should be bounded by configured execution concurrency rather than `O(N)` full canvases by default.

Example:

```text
10 requested assets
├─ #1 PASS -> materialize evidence -> reusable
├─ #2 PASS -> materialize evidence -> reusable
├─ #3 FAIL -> targeted repair/retry
├─ #4 PASS -> materialize evidence -> reusable
...
└─ #10 PASS -> materialize evidence -> reusable
```

A later concurrency policy may allow provider parallelism such as 1/2/4 workers, but it must be explicit and bounded. Correctness must not depend on execution order.

## Cache / invalidation direction

Cache identity should be content-addressed from the effective member inputs and relevant authoring contract/version, not only from display names.

A member may be reused only when its effective intent, required shared-set constraints and relevant pipeline/provider configuration are unchanged. Changing a shared palette or another set-wide invariant must invalidate only the members whose effective contract changed.

## Relationship to existing P8 breadth

P8-X0 is a reusable production foundation, not a replacement for later breadth work:

```text
P8-X0 AssetSet / batch foundation
 -> P8-B0 richer item icons
 -> P8-B1 props/furniture
 -> P8-B2 tileable blocks/terrain decoration
 -> P8-B3 autotile/variant consistency
 -> P8-B4 simple creatures
 -> owner promotion gate
 -> P8-B5 humanoids
 -> owner promotion gate
 -> P8-B6 animation/multi-frame consistency
```

Later children should reuse AssetSet where multiple related outputs are natural:

- item/icon variants: multiple independently usable assets,
- autotiles: fixed related tile members with set-level edge/slot constraints,
- creature/humanoid variants: related identities with bounded shared constraints,
- animation: ordered frames with temporal/multi-frame consistency requirements.

Animation remains behind its existing owner promotion gate; adding generic AssetSet does not silently authorize animation or humanoid scope.

## Acceptance direction for P8-X0

Before P8-X0 can advance:

- one set with multiple assets is deterministically materialized,
- each member can replay/QA independently,
- one intentionally failed member can be retried without regenerating unchanged successful members,
- manifest member ordering/digests are deterministic,
- bounded execution concurrency is explicit,
- batch gallery exposes per-member evidence,
- complexity telemetry can report both per-member and aggregate set cost,
- portable CI requires no live paid/network provider.

## Non-goals

P8-X0 does not by itself add:

- unbounded parallel model calls,
- sprite-atlas packing/runtime import,
- automatic perceptual style scoring,
- humanoid promotion,
- animation promotion,
- Trace2D integration.

Those remain separate product/owner decisions where already defined.