# P8-B4 Tile-Set AssetSet Breadth

Status: **implemented checkpoint; hand off to P8-B5 only after portable CI is green.**

P8-B4 proves that a small top-down terrain tile family can travel through the same bounded AssetSet request, consistency, scheduling, execution and retention seams already used by icons and props. It does not add a tile renderer, atlas authority, provider-side batch planner, or shared mutable raster surface.

## Representative retained tile family

`evidence/p8_b4/reference-tile-asset-set.v1.json` declares four independent 16x16 `terrain-tile` members:

- two grass center variants,
- one grass-to-dirt east-edge transition,
- one grass-to-dirt southeast-corner transition,
- one exact digest-pinned `top-down-rpg-tiles` style profile shared by every member,
- one exact digest-pinned `meadow-dirt-palette` palette profile shared by every member.

Every member still owns its own ArtIntent and single-asset execution. The set does not become one larger Canvas and no atlas packing or multi-tile raster authority is introduced.

## Semantic topology evidence

Tiles differ from isolated icons/props because their intended edge relationships matter. B4 therefore retains a provider-free evidence sidecar, `reference-tile-topology.v1.json`, describing a frozen 2x2 patch:

```text
grass-center-a        | grass-dirt-east-edge
----------------------+----------------------
grass-center-b        | grass-dirt-southeast-corner
```

Each retained member has four semantic edge labels (`top`, `right`, `bottom`, `left`). The checkpoint verifies that every internal horizontal and vertical neighbor pair declares matching labels and that the topology member order exactly matches the frozen AssetSet order.

This topology sidecar is **evidence for the B4 breadth checkpoint**, not a new canonical raster/runtime authority. It does not tell the renderer how to draw pixels and is not silently injected into the production executor.

## Deterministic vs perceptual seam authority

B4 can deterministically prove:

- exact member identity/order and request digests,
- exact 16x16 tile dimensions,
- exact `terrain-tile` class preservation through the existing single-asset seam,
- exact shared style and palette profile identity,
- exact declared semantic edge compatibility in the retained 2x2 topology,
- one execution attempt per member and isolated failure retention,
- zero provider calls/tokens and zero raster work added by the checkpoint.

B4 **cannot** deterministically claim that independently generated edge pixels are visually seamless merely because their semantic labels match. Pixel-level seam quality, tile repetition quality and style/palette appearance remain perceptual evidence. P8-B5 owns the batch preview/mobile review surface needed to inspect those outputs without converting human perception into deterministic QA truth.

## Failure-isolation probe

The provider-free checkpoint records one synthetic failure on `grass-dirt-southeast-corner`. The other three tile members must each execute exactly once and retain success. This preserves the AssetSet rule that one failed tile does not erase or restart successful siblings.

## Cost / performance boundary

B4 adds only bounded JSON validation/projection and a four-member provider-free execution seam probe. Runtime live work remains bounded by the existing AssetSet `max_concurrency`; there is no unbounded worker fan-out, no per-pixel topology copy, and no batch-global provider call.

The topology check is constant-sized in the retained B4 fixture and would be linear in tile/member count plus declared adjacency edges for a generalized representation. B4 intentionally does not introduce such a generalized production topology schema before preview evidence demonstrates that the requirement deserves promotion.

## Checkpoint

Run:

```bash
python -m evidence.p8_b4.checkpoint
```

The checkpoint fails closed if tile dimensions/class/order drift, the shared style/palette binding drifts, an internal declared semantic seam mismatches, the single-asset seam is bypassed, failure isolation changes, provider/token/raster work appears, or the core lane does not hand off to P8-B5.

Once portable CI is green, the next fixed child is **P8-B5 batch preview + mobile review evidence**.
