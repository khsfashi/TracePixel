# ArtIntent v1

`tracepixel.art-intent.v1` is the P3-S0 provider-neutral intent/composition contract above the frozen `PixelProgram v1` replay boundary.

It describes bounded requested facts and hints. It does **not** claim that recognizability, style quality or other perceptual judgments can be deterministically proven.

## Closed envelope

Every v1 document contains exactly:

```text
schema
asset_class
canvas
composition
```

`asset_class` is a bounded semantic label (1-64 Unicode code points), for example `potion`, `key`, `lantern` or `terrain_tile`. It is intent metadata, not a deterministic taxonomy or recognizability claim.

`canvas` reuses the P1 raster dimension contract: exact integer dimensions, positive, at most 4096 per axis.

`composition` always contains the same five keys:

- `occupied_bounds`: optional intended top-left half-open rectangle inside the canvas,
- `facing`: optional bounded orientation (`left`, `right`, `up`, `down`, `front`, `back`),
- `symmetry`: optional axis (`vertical`, `horizontal`, `both`) plus `hint` or `required`,
- `light_direction`: optional bounded 2D direction,
- `palette_budget`: optional exact maximum requested color count in `[1, 256]`.

When a field is irrelevant or unspecified, its value is JSON `null`; keys are not omitted. This keeps the machine-visible shape stable without pretending every asset uses every concept.

## Deterministic validation boundary

`validate_art_intent()` validates only objective contract facts:

- exact closed object shape,
- supported schema identity,
- bounded asset-class length,
- P1 canvas dimension rules,
- occupied rectangle integer geometry and containment,
- bounded enum values,
- palette-budget range.

Validation returns the original object without copying or normalization. It creates no `Canvas`, executes no `PixelProgram`, and creates no stage state.

P3-S0 does not define silhouette pixels, major forms, palette ramps, shading, semantic details, cleanup operations, stage transitions or evidence records. Those remain ordered P3-S1 through P3-S7 work.
