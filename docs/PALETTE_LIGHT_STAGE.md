# Palette / Light Ramp Stage v1

`tracepixel.palette-light-stage.v1` is the P3-S3 provider-neutral contract for declaring an exact finite palette, optional authored light-ramp relationships, and stage-local PixelProgram edits.

Its purpose is to constrain intentional color growth without turning one lighting or shading model into universal engine truth.

## Closed envelope

Every v1 document contains exactly:

```text
schema
stage
palette
ramps
program
```

- `schema` is exactly `tracepixel.palette-light-stage.v1`.
- `stage` is exactly `palette_light_ramp`.
- `palette` contains 1..256 exact RGBA8 colors, each named by one bounded authored `role`.
- `ramps` contains 0..32 optional ordered relationships between palette roles.
- `program` is an ordinary validated `tracepixel.pixel-program.v1` document.

Palette roles and ramp IDs are lowercase ASCII slugs of 1..32 characters. TracePixel does not define a fixed vocabulary such as `shadow`, `base`, `highlight`, `metal`, or `skin`; those meanings remain authored metadata.

Exact RGBA values are unique inside the palette. Multiple role names for the same exact color are rejected so one stage has one stable color identity.

## Palette authority for stage-local edits

Every exact RGBA written by the nested PixelProgram must already appear in `palette`.

The validator therefore prevents an edit from silently introducing an undeclared color while preserving the existing PixelProgram coordinate, batching, operation-order, and duplicate-coordinate semantics.

The palette may contain colors that the P3-S3 program does not write yet. This is intentional: later shading/detail stages can consume previously declared ramp colors without requiring redundant P3-S3 pixel rewrites.

An empty `program.operations` array is also valid. Declaring palette/ramp metadata is meaningful even when the major-form pixels already use the intended base colors.

## Authored light ramps, not computed brightness

Each ramp contains:

```text
id
colors
```

`colors` is an ordered list of 2..256 distinct palette-role references. The order is explicit authored light-level intent for later stages.

P3-S3 validates only the relationship graph:

- every referenced role exists,
- a role is not repeated inside one ramp,
- ramp IDs are unique,
- the number of ramps is bounded.

It deliberately does **not** compute luminance, sort RGB values, require monotonic channel values, infer a light direction, or claim that one color is perceptually lighter than another. A stylized palette may intentionally violate numeric brightness heuristics.

Geometric application of `ArtIntent.composition.light_direction` belongs to P3-S4 shading. Cross-stage enforcement of the S0 `palette_budget` belongs to the P3-S7 transition/orchestration boundary, where the input intent and stage identities are explicit; P3-S3 does not duplicate those fields as a second authority.

## Deterministic validation boundary

`validate_palette_light_stage()`:

- fails closed on the stage, palette-color, and light-ramp envelopes,
- reuses the P1 RGBA8 validation contract for palette colors,
- validates the nested PixelProgram through `validate_pixel_program()`,
- rebases nested PixelProgram failures under `$.program`,
- enforces unique bounded role/ramp identities and exact palette colors,
- validates ramp references without interpreting perceptual brightness,
- scans every stage-local edited pixel once for exact palette membership,
- returns the original object without copying or normalization,
- does not execute the program or allocate raster state.

Validation is `O(palette + ramp_references + edited_pixels)` with `O(palette + ramps)` bounded identity/color state and no per-pixel collection.

P3-S3 does not yet define shading placement, semantic details, outline/cleanup, complete stage ordering/skip semantics, transition snapshots, or perceptual correctness. Those remain P3-S4 through P3-S7.
