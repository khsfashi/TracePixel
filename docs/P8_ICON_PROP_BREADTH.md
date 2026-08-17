# P8-B3 Icon / Prop AssetSet Breadth

Status: **implemented checkpoint; hand off to P8-B4 only after portable CI is green.**

P8-B3 proves that representative inventory icons and scene props can coexist in one bounded AssetSet without adding a second authoring path, a class-specific batch executor, provider work, or raster authority.

## Why B3 does not add an asset-class enum

`ArtIntent v1` already retains `asset_class` as a bounded non-empty string and the P8 request/schedule/execution contracts are intentionally class-agnostic. Adding a global `item-icon | scene-prop` enum only for this milestone would make the single-asset contract less extensible and duplicate policy that belongs in retained task/profile evidence.

B3 therefore treats breadth as an integration/evidence requirement rather than a new parallel runtime.

## Retained representative set

`evidence/p8_b3/reference-icon-prop-asset-set.v1.json` declares four members in one set:

- two `item-icon` requests on independent 16x16 canvases,
- two `scene-prop` requests on independent 24x24 canvases,
- one exact digest-pinned `small-rpg-objects` style profile shared by all four members,
- declared-order scheduling, bounded concurrency, isolated member failure, and finite aggregate budgets inherited from AssetSet v1.

The class-specific composition remains member-local. Icons and props are not forced to share canvas dimensions, occupied bounds, facing, symmetry, or palette budgets merely because they share a set-level style identity.

## Existing pipeline reused

The B3 checkpoint derives and validates the same surfaces already frozen earlier in P8:

```text
AssetSet v1
 -> AssetRequest v1 validation + canonical request digests
 -> AssetSetRequest v1 binding
 -> deterministic bounded AssetSetSchedule v1
 -> AssetSet consistency projection
 -> existing SingleAssetExecutor seam per member
 -> isolated retained execution report
```

There is no icon batch renderer and no prop batch renderer. `asset_class` reaches the existing single-asset execution seam unchanged.

## Failure-isolation probe

The retained provider-free checkpoint records one synthetic failure on `lantern-prop`. The other icon and prop members must each execute exactly once and retain success. This is not a quality claim; it proves that introducing a second asset class does not weaken the previously frozen member-local failure boundary.

## Deterministic vs perceptual authority

B3 deterministically proves only structural facts such as:

- exact member identity/order/request digests,
- exact `asset_class` values in the retained fixture,
- independent 16x16 and 24x24 member canvases,
- exact shared style-profile identity,
- one execution attempt per member and isolated failure retention,
- zero added provider calls/tokens and zero raster work inside the checkpoint.

Referencing the same style profile still does **not** prove that generated icon and prop pixels look stylistically identical. That appearance claim remains `perceptual-evidence-required` under the P8-B2 authority boundary.

## Cost / performance boundary

B3 adds only bounded JSON/profile/request projection and a provider-free seam probe. It does not introduce class dispatch in the production executor, extra provider fan-out, shared mutable pixels, or another canonical raster copy.

The existing complexity remains dominated by the already bounded per-member request/profile validation and AssetSet execution bookkeeping. No new unbounded collection or per-pixel allocation is introduced.

## Checkpoint

Run:

```bash
python -m evidence.p8_b3.checkpoint
```

The checkpoint fails closed if the retained class mix, independent canvas sizes, shared style binding, single-asset seam identity, failure isolation, zero provider/token/raster additions, or core-lane handoff drift.

Once portable CI is green, the next fixed child is **P8-B4 tile-set breadth**.
