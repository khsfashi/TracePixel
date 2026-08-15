# Shading Stage v1

`tracepixel.shading-stage.v1` is the P3-S4 provider-neutral contract for bounded directional shading over the frozen PixelProgram v1 replay boundary.

It consumes already-authored deterministic context instead of inventing a new lighting model:

- S0 `ArtIntent.composition.light_direction` and `occupied_bounds`,
- S3 exact palette roles and authored light-ramp order,
- one S4 PixelProgram operation per declared shading application.

The contract does not estimate luminance, infer normals/materials, or claim that a result is perceptually well lit.

## Closed envelope

Every v1 document contains exactly:

```text
schema
stage
applications
program
```

- `schema` is exactly `tracepixel.shading-stage.v1`.
- `stage` is exactly `shading`.
- `applications` contains 0..64 bounded shading declarations.
- `program` is an ordinary validated `tracepixel.pixel-program.v1` document.

Each application contains exactly:

```text
id
ramp_id
source_role
target_role
relation
```

`applications[i]` maps positionally to `program.operations[i]`. This preserves PixelProgram as the sole coordinate/raster-write authority rather than duplicating pixel masks in the shading metadata.

## Authored ramp semantics

S3 light-ramp order is authored light-level intent, not computed RGB brightness. S4 gives that order one deterministic directional meaning:

- `toward_light` must move from a lower ramp index to a higher ramp index,
- `away_from_light` must move from a higher ramp index to a lower ramp index.

The validator never sorts colors by luminance or channel values. Stylized ramps remain valid even when their numeric RGB values are not monotonic.

The source and target role must belong to the referenced S3 ramp. The transition must preserve authored alpha so shading cannot silently become a silhouette/occupancy mutation.

Every pixel written by the mapped PixelProgram operation must use the exact RGBA value of the declared `target_role`.

S4 does not prove that the input pixel currently has `source_role`. That requires an explicit authoritative input-stage state and belongs to the P3-S7 transition/evidence boundary.

## Deterministic light-side geometry

Non-empty S4 shading requires S0 to provide both `light_direction` and `occupied_bounds`.

The occupied rectangle center is the deterministic spatial anchor. For each edited pixel, TracePixel uses the pixel center and one of eight integer light vectors:

```text
top          ( 0, -1)
top_right    ( 1, -1)
right        ( 1,  0)
bottom_right ( 1,  1)
bottom       ( 0,  1)
bottom_left  (-1,  1)
left         (-1,  0)
top_left     (-1, -1)
```

The validator computes an exact integer dot product using doubled pixel-center / bounds-center coordinates; no float math is required.

- `toward_light` pixels may lie on the center line or the toward-light half-plane.
- `away_from_light` pixels may lie on the center line or the away-from-light half-plane.
- pixels outside the authored occupied bounds are rejected.

This is intentionally only a coarse, objective placement rule. It does not model surface normals, cast shadows, curvature, specular response, ambient occlusion, or perceptual lighting quality.

## Context validation

`validate_shading_stage(stage, *, art_intent, palette_light_stage)` validates both context documents through their existing validators before using them.

It also requires:

- S4 PixelProgram canvas == S0 ArtIntent canvas,
- S3 PixelProgram canvas == S0 ArtIntent canvas,
- application count == PixelProgram operation count,
- unique bounded application IDs,
- valid referenced ramp/role identities,
- non-empty pixel edits for every non-empty application.

Invalid nested context paths are rebased under `$context.art_intent` or `$context.palette_light_stage`; invalid stage-local PixelProgram paths are rebased under `$.program`.

Validation is linear in the validated context plus edited S4 pixels and uses only bounded palette/ramp/application identity maps. It executes no PixelProgram and allocates no Canvas or per-pixel state collection.

## Scope boundary

P3-S4 does **not** add:

- semantic-detail operations,
- outline/cleanup semantics,
- stage ordering or skip records,
- authoritative input snapshots or source-role replay proof,
- preview/evidence snapshots,
- provider/model or VLM integration,
- GPU/image dependencies or self-hosted runner requirements.

Those remain ordered P3-S5 through P3-S7 or later phases.
