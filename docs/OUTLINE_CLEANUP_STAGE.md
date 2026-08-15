# Outline / Cleanup Stage v1

`tracepixel.outline-cleanup-stage.v1` is the P3-S6 provider-neutral contract for explicit outline and cleanup work after semantic details.

The stage deliberately does **not** define what a good outline looks like, how thick it should be, whether corners should be rounded, or which isolated pixels are aesthetically undesirable. Those are authored/perceptual choices unless a later deterministic QA rule is explicitly requested.

The frozen P2 `set_pixels` operation remains the only raster-write primitive. S6 adds bounded action identity and authored `outline` / `cleanup` classification so later evidence and repair can localize the work without adding a second raster authority.

## Closed envelope

Every v1 document contains exactly:

```text
schema
stage
actions
program
```

- `schema` is exactly `tracepixel.outline-cleanup-stage.v1`.
- `stage` is exactly `outline_cleanup`.
- `actions` contains 0..64 declarations.
- `program` is an ordinary validated `tracepixel.pixel-program.v1` document.

Each action contains exactly:

```text
id
kind
```

- `id` is an authored lowercase slug of 1..32 characters.
- `kind` is exactly `outline` or `cleanup`.

`actions[i]` maps positionally one-to-one to `program.operations[i]`. PixelProgram remains the sole coordinate and raster-write authority.

The `kind` value is an authored classification. Validation does not claim that an `outline` patch is geometrically on an object boundary or that a `cleanup` patch objectively improves the image. Authoritative input/output comparison is intentionally deferred to P3-S7, while reusable adjacency/outline diagnostics belong to P4.

## Bounded raw patches

Every declared action maps to one non-empty `set_pixels` operation containing at most 64 serialized pixel edits.

The limit bounds authored work and future repair locality rather than guessing a universal visual radius. PixelProgram operation order, pixel order, and duplicate-coordinate last-write-wins semantics remain unchanged. Duplicate writes are legal and each serialized edit counts against the 64-edit budget.

An empty S6 stage (`actions: []` and no program operations) is valid. P3-S7 owns the later distinction between an executed no-op stage and an explicitly skipped stage.

## Palette relationship

`validate_outline_cleanup_stage(stage, *, palette_light_stage=...)` consumes the already-authored P3-S3 palette/light document.

It requires:

- the S6 PixelProgram canvas to equal the S3 PixelProgram canvas,
- every S6 written RGBA value to exactly match a color declared in the S3 palette,
- the supplied S3 context itself to pass its existing validator.

This prevents outline/cleanup work from silently expanding the color vocabulary after the palette stage.

Transparent or translucent writes are not given special semantic meaning by S6. They are allowed only when that exact RGBA value is already present in the S3 palette. For example, erasing to `[0, 0, 0, 0]` is valid only if that color was deliberately declared. S6 does not invent a hidden erase primitive or canonical transparent color.

## Deliberate non-authority

S6 does not deterministically enforce:

- outline thickness,
- outline continuity or placement,
- jaggedness/smoothness preferences,
- anti-aliasing style,
- whether a pixel is visually stray,
- silhouette preservation,
- recognizability, readability, or aesthetic quality.

Some exact structural facts can be measured later in P4, but they become pass/fail policy only when an explicit task contract requests them. Perceptual style remains outside deterministic truth.

S6 also does not know the authoritative input raster. Therefore it cannot prove whether a cleanup removed a pre-existing pixel, whether an outline replaced a specific source color, or whether unaffected pixels stayed stable. P3-S7 introduces the transition/evidence authority needed for those comparisons.

## Validation and complexity

Runtime validation rejects:

- unknown schema/stage identities,
- missing/extra fields,
- more than 64 actions,
- invalid or duplicate action IDs,
- action kinds other than `outline` / `cleanup`,
- invalid S3 context,
- invalid stage-local PixelProgram,
- canvas mismatch,
- action/operation count mismatch,
- empty mapped patches,
- more than 64 serialized edits in one action,
- colors absent from the declared S3 palette.

Validation is `O(palette + actions + edited_pixels)` with bounded `O(palette + actions)` identity/color state. It does not execute PixelProgram, allocate a Canvas, deep-copy input, or build a per-pixel state collection.

## Scope boundary

P3-S6 does **not** add:

- geometric outline generation,
- smoothing or cleanup heuristics,
- a new PixelProgram operation,
- subjective style thresholds,
- full stage ordering/skip records,
- authoritative input/output transition snapshots,
- preview evidence,
- deterministic P4 shape/outline analyzers,
- provider/model or VLM integration,
- GPU/image dependencies or self-hosted runner requirements.

Those remain P3-S7, P4, or later phases.
