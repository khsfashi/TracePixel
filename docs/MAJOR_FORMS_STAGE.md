# Major Forms Stage v1

`tracepixel.major-forms-stage.v1` is the P3-S2 provider-neutral contract for splitting coarse construction into a bounded set of large form identities after the silhouette stage.

Its purpose is structural, not perceptual: it makes the form boundary explicit enough for deterministic replay and later stage-local repair without introducing a domain-specific vocabulary such as `blade`, `wing`, `handle`, `eye`, or `body` into the engine contract.

## Closed envelope

Every v1 document contains exactly:

```text
schema
stage
forms
program
```

- `schema` is exactly `tracepixel.major-forms-stage.v1`.
- `stage` is exactly `major_forms`.
- `forms` contains 1..16 domain-neutral form identities.
- `program` is an ordinary validated `tracepixel.pixel-program.v1` document.

Each form contains only a stable `id`. IDs are lowercase ASCII slugs of 1..32 characters and must be unique.

## Positional form-to-operation identity

P3-S2 deliberately avoids a second coordinate list or region-mask authority.

For v1, `forms[i]` identifies `program.operations[i]`. The two arrays therefore have identical lengths, and the existing PixelProgram operation order is also the deterministic form application order.

This remains compact because PixelProgram v1 intentionally exposes only the `set_pixels` operation. One bounded batch is sufficient to express one coarse form without adding operation-index lists, duplicated canvases, masks, or object-specific schemas.

Overlapping coordinates are legal. When the stage is executed later through the existing ordered PixelProgram semantics, a later form may deliberately overwrite pixels written by an earlier form.

## Flat construction invariant

Each form operation:

1. contains at least one pixel edit,
2. uses only fully opaque pixels (`alpha == 255`),
3. uses one exact RGBA construction color inside that form.

Different forms may use different or identical construction colors. These colors identify coarse construction only; they do not freeze palette roles, light ramps, shading, or final style. Those belong to later P3 children.

The validator does not impose a deterministic minimum area. A form being perceptually “major”, recognizable, connected, well-proportioned, or aesthetically useful is not an objective fact at this boundary.

## Deterministic validation boundary

`validate_major_forms_stage()`:

- fails closed on the stage and form envelopes,
- validates the nested program through `validate_pixel_program()`,
- rebases nested PixelProgram failures under `$.program`,
- enforces the 16-form cap and unique bounded IDs,
- enforces the positional 1:1 form/operation mapping,
- scans each edited pixel once to enforce non-empty/opaque/flat form construction,
- returns the original object without copying or normalization,
- does not execute the program or allocate a second pixel/region representation.

Validation is `O(forms + edited_pixels)` with `O(forms)` ID state and no per-pixel collection.

P3-S2 does not yet define palette/light relationships, shading, semantic details, outline/cleanup, full stage ordering/skip rules, transition snapshots, or perceptual correctness. Those remain P3-S3 through P3-S7.
