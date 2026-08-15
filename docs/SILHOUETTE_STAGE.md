# Silhouette Stage v1

`tracepixel.silhouette-stage.v1` is the P3-S1 provider-neutral contract for the first authored pixel stage after `ArtIntent v1`.

Its job is deliberately narrow: represent the primary occupied shape before major forms, palette/light relationships, shading, semantic detail or cleanup are introduced.

Silhouette is a **stage identity and structural authoring boundary**. Passing this validator does not claim that the shape is recognizable, attractive, correctly oriented or semantically faithful.

## Closed envelope

Every v1 document contains exactly:

```text
schema
stage
program
```

- `schema` is exactly `tracepixel.silhouette-stage.v1`.
- `stage` is exactly `silhouette`.
- `program` is an ordinary validated `tracepixel.pixel-program.v1` document.

The stage contract does not define a second mask/raster authority. Exact pixel coordinates, RGBA8 validation, canvas dimensions, operation ordering and duplicate-coordinate behavior continue to come from the frozen P1/P2 contracts.

## Flat silhouette invariant

P3-S1 adds only three constraints above a valid PixelProgram:

1. at least one pixel edit must exist,
2. every edited pixel must be fully opaque (`alpha == 255`),
3. every edited pixel must use the same exact RGBA value.

A transparent blank canvas plus one flat opaque color therefore expresses only occupancy/shape. Multiple `set_pixels` batches and duplicate coordinates remain valid when they preserve the same flat color, so the existing ordered PixelProgram semantics are not replaced.

The exact construction color is not a final palette commitment. Later P3 stages may deliberately replace it.

## Deterministic validation boundary

`validate_silhouette_stage()`:

- fails closed on the stage envelope,
- validates the nested program through `validate_pixel_program()` rather than duplicating P1/P2 numeric rules,
- rebases nested PixelProgram failures under `$.program`,
- checks only the non-empty/opaque/flat-color silhouette invariants,
- returns the original object without copying or normalization,
- does not execute the program or create/mutate a `Canvas`.

P3-S1 does not yet enforce recognizability, facing, symmetry, intended occupied bounds, major forms, palette roles, lighting, shading, semantic details, outline/cleanup, stage ordering, skip semantics, transition snapshots or evidence records. Those remain later P3 children or deterministic QA work.
