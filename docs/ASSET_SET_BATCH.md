# AssetSet / Batch Authoring

Status: **P8-X0 and P8-R0 complete; P8-B0 defines the immutable multi-asset request/schedule boundary.** Runtime execution/retention remains P8-B1.

TracePixel keeps one constrained pixel asset as the authoritative authoring unit:

```text
instruction + ArtIntent + digest-pinned profile context
 -> existing single-asset stage/provider path
 -> Canvas
 -> deterministic QA
 -> preview/evidence
```

Batch production must scale that path without creating a second drawing engine, hidden shared raster state, or execution-order-dependent correctness.

## P8 contract stack

```text
AssetSet v1
 -> AssetRequest v1 per member
 -> AssetSetRequest v1 digest manifest
 -> AssetSetSchedule v1 deterministic dispatch queue
 -> P8-B1 isolated member execution + retention
 -> P8-B2 cross-asset consistency
 -> P8-B3/B4 icon, prop and tile breadth
 -> P8-B5 batch preview/mobile review
 -> P8-B6 checkpoint/postmortem
```

The active parent is issue #92. The fixed child order is:

```text
P8-X0 -> P8-R0 -> P8-B0 -> P8-B1 -> P8-B2 -> P8-B3 -> P8-B4 -> P8-B5 -> P8-B6
```

## P8-X0 AssetSet authority

`tracepixel.asset-set.v1` freezes:

- stable set identity,
- explicit declared member order,
- immutable shared style/palette/morphology profile references,
- the existing `single-asset-pipeline` as member authority,
- `isolate-member` failure policy,
- explicit finite `max_concurrency`,
- finite aggregate provider-call, pixel-edit and wall-time budgets.

AssetSet metadata is context and scheduling policy. It is never pixel/raster authority.

## P8-R0 research/profile boundary

Unfamiliar forms resolve explicitly to either a retained known profile or a bounded research request. Reusable morphology/form knowledge is versioned and digest-pinned. Source-observed facts, inferred constraints, artistic conventions and unknowns remain separate.

Research/profile context informs member authoring but never copies source imagery into canonical generated assets or becomes competing raster authority.

## P8-B0 AssetRequest

`tracepixel.asset-request.v1` is the immutable effective input for one member:

```text
{
  schema,
  instruction,
  art_intent,
  profile_refs[]
}
```

The request deliberately contains both `instruction` and the existing `ArtIntent`.

`ArtIntent` describes structural authoring intent such as canvas, occupied bounds, facing, symmetry, light direction and palette budget. It does not encode every semantic variant. For example, a red healing potion and a blue mana potion may have identical structural ArtIntent while still requiring distinct semantic instructions and therefore distinct cache identities.

Every member profile reference must exactly match one digest-pinned profile declared by the parent AssetSet. A member cannot silently introduce an unshared or differently digested profile.

## P8-B0 AssetSetRequest manifest

`tracepixel.asset-set-request.v1` binds every declared AssetSet member, in exact declared order, to:

- `member_id`,
- exact `request_ref`,
- canonical `request_sha256`.

The manifest also pins the canonical `asset_set_sha256`.

Before scheduling, every referenced request payload is loaded and validated. Missing payloads, extra payloads, member reordering, request-ref substitution, changed request bytes/semantics, invalid ArtIntent, or profile-ref drift fail closed.

This gives member-level content-addressed invalidation: changing one member request changes that member digest and the set-request manifest, but unchanged sibling request payloads remain independently identifiable and reusable by later execution/cache logic.

## P8-B0 deterministic schedule

`tracepixel.asset-set-schedule.v1` is an immutable projection of the validated AssetSet + request manifest. It records:

- canonical AssetSet and request-manifest digests,
- `single-asset-pipeline` member authority,
- `declared-member-order`,
- `declared-order-bounded-concurrency` dispatch policy,
- `isolate-member` failure policy,
- exact finite aggregate budget,
- exact `max_concurrency`,
- zero-based member ordinals and request digests.

The dispatch policy is a **declared-order admission queue with a bounded number of live workers**, not completion-order authority and not fixed barrier waves. A later P8-B1 executor may start the next declared member when a slot becomes free, but completion timing must never reorder member identity or change correctness.

For `N` members and concurrency `C`:

- schedule construction/bookkeeping is `O(N)`,
- schedule memory is `O(N)` small metadata,
- later live raster/provider working state should be bounded by `O(C)` members rather than retaining all `N` canvases by default.

## Runtime-state exclusion

P8-B0 schedules intentionally contain no:

- member `status`,
- provider response,
- PixelProgram,
- Canvas/RGBA data,
- QA result,
- output artifact,
- completion timestamp/order,
- retry/repair state.

Those belong to P8-B1 isolated execution/retention. Keeping them out of the scheduling contract prevents P8-B0 from becoming a second runtime/result authority.

## Consistency and review boundaries

P8-B2 owns cross-asset style/palette/profile consistency contracts. Objective rules may later be deterministic when explicitly measurable; aesthetic/style judgment remains perceptual/human unless a separate frozen measurable rule is established.

P8-B5 owns batch preview/mobile review. Aggregate views must never erase per-member evidence or convert human perception into deterministic QA truth.

## Non-goals of P8-B0

P8-B0 does not:

- invoke a provider,
- execute a member schedule,
- create raster authority,
- implement parallel worker/runtime state,
- retain success/failure results,
- score visual consistency,
- broaden to creatures/humanoids/animation early,
- start Trace2D integration.

Those remain in their fixed later lanes and owner-gate boundaries.
