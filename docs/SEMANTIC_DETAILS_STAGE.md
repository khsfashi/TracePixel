# Semantic Details Stage v1

`tracepixel.semantic-details-stage.v1` is the P3-S5 provider-neutral contract for small, high-information edits after coarse structure and shading have stabilized.

The stage deliberately does **not** introduce a domain object library such as `eye`, `rune`, `gem`, `handle`, or `button` operations. The frozen P2 `set_pixels` operation remains the only raster-write primitive. S5 adds only a bounded semantic locator around each raw patch so later evidence/repair can identify which authored detail changed.

## Closed envelope

Every v1 document contains exactly:

```text
schema
stage
details
program
```

- `schema` is exactly `tracepixel.semantic-details-stage.v1`.
- `stage` is exactly `semantic_details`.
- `details` contains 0..64 declarations.
- `program` is an ordinary validated `tracepixel.pixel-program.v1` document.

Each detail contains only:

```text
id
```

`id` is an authored lowercase slug of 1..32 characters. TracePixel does not interpret it through a fixed semantic vocabulary. Names such as `bottle_glint`, `seal_mark`, or `rune_tip` are locators for evidence and later targeted repair, not engine-level object types.

`details[i]` maps positionally one-to-one to `program.operations[i]`. PixelProgram remains the sole coordinate and raster-write authority.

## Bounded raw-patch escape hatch

Every non-empty detail maps to one non-empty `set_pixels` operation containing at most 64 serialized pixel edits.

The bound is deliberately on the authored patch payload rather than on a guessed visual concept. It keeps one semantic edit compact and localizable without pretending deterministic code can prove that a mark is perceptually "small" or "high information".

PixelProgram's existing ordering and duplicate-coordinate semantics remain unchanged. Duplicate writes are legal and count against the 64-edit budget because the serialized work itself is what is bounded.

## Palette relationship

`validate_semantic_details_stage(stage, *, palette_light_stage=...)` consumes the already-authored P3-S3 palette/light document.

It requires:

- the S5 PixelProgram canvas to equal the S3 PixelProgram canvas,
- every S5 written RGBA value to exactly match one color declared in the S3 palette,
- the S3 context itself to pass its existing validator.

This prevents semantic detail work from silently expanding color vocabulary after the palette stage. S5 does not require a light ramp or infer brightness relationships.

## Deliberate non-authority

S5 does not prove that a detail is recognizable, aesthetically useful, correctly placed, or semantically faithful to its `id`.

It also does not yet prove that a patch preserves the previous silhouette/occupancy. P3-S7 will introduce authoritative input-stage identity/replay evidence, which is the correct place to compare before/after raster state rather than guessing source pixels inside S5.

No alpha restriction is imposed beyond the existing RGBA8 and palette contracts. If a palette intentionally contains transparent or translucent colors, S5 may use them; later transition/QA policy decides whether that is acceptable for a particular asset contract.

## Validation and complexity

Runtime validation rejects:

- unknown schema/stage identities,
- missing/extra fields,
- more than 64 details,
- invalid or duplicate detail IDs,
- invalid S3 context,
- invalid stage-local PixelProgram,
- canvas mismatch,
- detail/operation count mismatch,
- empty mapped patches,
- more than 64 edits in one detail,
- colors absent from the declared S3 palette.

Validation is `O(palette + details + edited_pixels)` with bounded `O(palette + details)` identity/color state. It does not execute PixelProgram, allocate a Canvas, deep-copy input, or build a per-pixel state collection.

## Scope boundary

P3-S5 does **not** add:

- a semantic object/shape library,
- geometric convenience operations,
- perceptual recognizability/style rules,
- outline/cleanup semantics,
- full stage ordering/skip records,
- authoritative input/output transition snapshots,
- preview evidence,
- provider/model or VLM integration,
- GPU/image dependencies or self-hosted runner requirements.

Those remain P3-S6, P3-S7, or later phases.
