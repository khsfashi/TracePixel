# P6-V1 Stage Contact Sheet

P6-V1 turns authored stage previews into one deterministic review surface without decoding, resampling, or re-encoding their pixels.

## Contract

`tracepixel.preview.build_stage_contact_sheet(...)` accepts the existing `PreviewStageArtifact` sequence used by P6-V0. It selects `stage-image` PNG artifacts, requires at most one image per P3 stage, sorts them by the fixed P3 stage order, and emits schema `tracepixel.stage-contact-sheet.v1`.

The materialized payload is:

```text
manifest.json
stage-contact-sheet.svg
```

The SVG uses each stage PNG at its natural width and height and embeds the exact PNG bytes as a base64 data URI. Only layout/card/label markup is added around those images. No PNG decoder is required and there is no raster recomposition step.

## Mobile-readable presentation cells

A P6-V5 phone review exposed that the original cell width was derived only from the tiny source PNG width, so long labels such as `semantic details` and `outline cleanup` could visually overflow their cards after the whole SVG was fit to a phone viewport.

The presentation layout now:

- reserves a deterministic minimum cell width of 112 SVG units,
- separates the numeric stage index from the stage label,
- reserves 30 SVG units for the label area,
- uses a fixed 10-unit stage-label font size,
- keeps the normal six-stage / three-column reference sheet within a 400-unit natural width,
- continues to place every source stage PNG at its exact natural dimensions.

This is a presentation-only geometry change. Source PNG bytes, stage order and raster authority are unchanged.

The manifest records fixed stage order; exact source path, byte count and SHA-256; source PNG dimensions read from IHDR; deterministic layout including the minimum cell width and label sizing; exact SVG digest; and explicit authority separation.

## Determinism and bounds

- Caller order does not affect the sheet; P3 stage order is canonical.
- One contact-sheet image is allowed per authored stage, so the sheet is bounded by the six P3 stages.
- Column count is an exact integer from 1 through the number of P3 stages.
- Stage PNGs must be baseline non-interlaced RGBA8 PNGs within the existing 4096-per-axis bound.
- The writer refuses a non-empty output directory so stale review files cannot leak into a new sheet.

## Pixel and authority boundary

- Source stage PNG bytes are embedded byte-for-byte.
- Images are placed at natural pixel dimensions; `source_image_scaling` remains `none`.
- The authoritative `Canvas`/RGBA state and P3 stage replay evidence remain unchanged.
- The contact sheet is presentation state, not deterministic QA authority.
- No perceptual or VLM judgment is introduced; G4 remains unresolved.

## Portable checkpoint

```bash
python -m evidence.p6_v1.checkpoint
```

The checkpoint rebuilds the six provider-free P3 stage previews, constructs the sheet deterministically, verifies stage order and exact PNG SHA-256 values, and materializes the result to a temporary directory. Unit coverage additionally freezes the phone-readable cell geometry so the label-overflow regression cannot silently return.
