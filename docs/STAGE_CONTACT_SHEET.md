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

The manifest records:

- fixed stage order,
- exact source path, byte count and SHA-256 for every stage image,
- source PNG dimensions read only from IHDR,
- deterministic sheet layout,
- exact SVG byte count and SHA-256,
- explicit authority separation.

## Determinism and bounds

- Caller order does not affect the sheet; P3 stage order is canonical.
- One contact-sheet image is allowed per authored stage, so the sheet is bounded by the six P3 stages.
- Column count is an exact integer from 1 through the number of P3 stages.
- Stage PNGs must be baseline non-interlaced RGBA8 PNGs with dimensions in the existing TracePixel 4096-per-axis bound.
- The writer refuses a non-empty output directory so stale review files cannot leak into a new sheet.

## Pixel and authority boundary

The contact sheet is presentation state only.

- Source stage PNG bytes are embedded byte-for-byte.
- Images are placed at their natural pixel dimensions; `source_image_scaling` is recorded as `none`.
- The authoritative `Canvas`/RGBA state and P3 stage replay evidence remain unchanged.
- The contact sheet does not become deterministic QA authority.
- No perceptual or VLM judgment is introduced; G4 remains unresolved.

## Portable checkpoint

P6-V1 reuses committed/provider-free P3-S7 staged evidence:

```bash
python -m evidence.p6_v1.checkpoint
```

The checkpoint rebuilds the six stage previews from the deterministic P3 fixture, constructs the sheet twice, requires byte-identical output, verifies fixed stage order and each embedded PNG SHA-256 against the P3 export metadata, and materializes the result to a temporary directory.

To keep a generated copy:

```bash
python -m evidence.p6_v1.checkpoint --output out/p6-v1-reference
```

No provider call, network access, secret, GPU, VLM, or self-hosted runner is required.

## Scope boundary

P6-V1 stops at stage progression composition. Presenting deterministic QA and Agent-complexity evidence beside imagery is P6-V2; static HTML is P6-V3; GitHub artifact publishing is P6-V4; the proven mobile review flow is P6-V5; optional home-PC preview execution remains behind G6 at P6-V6.
