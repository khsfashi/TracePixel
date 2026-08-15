# Pixel IR Contract

P2 freezes the public serialized `PixelProgram` boundary without introducing provider/model state or a second pixel authority.

## Authority

The v1 serialized document is JSON-compatible data identified by:

```text
tracepixel.pixel-program.v1
```

The machine-readable structural contract is `schemas/pixel-program.v1.schema.json`. Python `TypedDict` declarations in `tracepixel.model` mirror that shape for library/tooling ergonomics; Python source code, callables and provider SDK objects are not canonical program state.

A concrete program flows toward the existing P1 raster authority through explicit validation, canonical serialization when persisted/transmitted, and deterministic execution:

```text
PixelProgram(v1)
 -> P2-IR1 validation
 -> P2-IR3 canonical JSON bytes (when serialized)
 -> P2-IR2 deterministic executor
 -> Canvas / authoritative RGBA8
```

`ArtIntent` and `StagePlan` remain architectural upstream concepts, but P2 does not freeze their serialized shape yet. Stage semantics belong to P3 and should not leak into the minimal replay program early.

## PixelProgram v1

Minimal example:

```json
{
  "schema": "tracepixel.pixel-program.v1",
  "canvas": {
    "width": 2,
    "height": 1
  },
  "operations": [
    {
      "op": "set_pixels",
      "pixels": [
        [0, 0, 255, 0, 0, 255],
        [1, 0, 0, 0, 0, 0]
      ]
    }
  ]
}
```

The v1 envelope has exactly three fields:

- `schema`: exact version discriminator,
- `canvas`: requested `width` and `height`,
- `operations`: ordered operation array.

There is deliberately no unbounded metadata/extensions bag in v1. Evidence, provider transcripts, prompts and perceptual-review state stay outside canonical replay data.

## Initial operation vocabulary

P2-IR0 freezes one exact low-level operation:

```text
set_pixels
```

Each pixel edit is the six-integer JSON array:

```text
[x, y, r, g, b, a]
```

This representation is intentionally close to the P1 transactional batch authority while avoiding one verbose object/key set per pixel. `operations` order and each `pixels` array order are explicit serialized order. Duplicate coordinates remain valid and execution preserves the P1 ordered last-write-wins contract.

`set_pixels` alone can express any finite RGBA raster, so P2 does not guess line/rect/fill/art-aware operations before the P2-IR4 compactness evidence. Additional operation kinds require an intentional schema/version decision rather than an open-ended command bag.

## P2-IR1 runtime validation

`tracepixel.model.validate_pixel_program(program)` is the dependency-free runtime validation authority for the currently supported PixelProgram version.

Validation is side-effect-free: it creates no `Canvas`, performs no raster mutation and returns the same input object after success rather than deep-copying or normalizing it. The executor and serializer validate the supplied object at their boundary instead of treating mutable Python objects as permanently certified.

The validator enforces:

- exact JSON container shapes (`dict` objects and `list` arrays),
- exact closed field sets at the program, canvas and operation levels,
- schema identity `tracepixel.pixel-program.v1`,
- operation identity `set_pixels`,
- P1 canvas size semantics, including exact integers and the 4096-per-axis bound,
- exactly six values per pixel edit,
- P1 exact-integer coordinate semantics and canvas-relative bounds,
- P1 straight-alpha RGBA8 exact-integer channel range `[0, 255]`.

Python `bool` values are rejected anywhere an integer is required because P1 deliberately uses exact integer semantics rather than Python's `bool`-is-an-`int` inheritance behavior.

Empty operation arrays and empty `pixels` arrays are valid. Duplicate coordinates are also valid; validation neither deduplicates nor reorders them.

Failures raise `PixelProgramValidationError` with stable `code` and JSON-style `path` fields. Current rejection codes are:

- `invalid_type`,
- `invalid_fields`,
- `unsupported_schema`,
- `invalid_canvas`,
- `unsupported_operation`,
- `invalid_edit`,
- `invalid_coordinate`,
- `invalid_color`.

These error identifiers are intended for deterministic tooling and repair loops. Human-readable error text may contain more detail, but callers should branch on `code` and `path` rather than parse the message.

## P2-IR2 deterministic execution

`tracepixel.model.execute_pixel_program(program)` is the deterministic replay entry point for an in-memory supported v1 program.

Execution follows one fixed order:

1. validate the complete input with `validate_pixel_program`,
2. construct one fresh P1 `Canvas` from the validated dimensions,
3. execute each serialized operation in order through `Canvas.set_pixels()`,
4. return that `Canvas` as the only authoritative raster result.

A validation failure occurs before `Canvas` construction, so an invalid program cannot expose partially mutated raster authority. Every successful call returns a fresh independent `Canvas`; replay requires no provider/model and does not mutate, normalize, reorder or deduplicate the input program.

The executor does not implement a second pixel writer. Its private lazy sequence adapter translates each already-validated `[x, y, r, g, b, a]` edit into the existing P1 `(x, y, RGBA8)` batch shape only when `Canvas.set_pixels()` consumes it. This avoids materializing a second O(N) Python edit collection while retaining P1's compact packed transaction staging, validation and ordered last-write-wins semantics.

Empty operation arrays produce a transparent canvas of the declared dimensions. Empty `set_pixels` batches are no-ops. Operation order, edit order and duplicates remain semantically significant.

## P2-IR3 canonical serialization and round-trip replay

`tracepixel.model.serialize_pixel_program(program)` validates the complete v1 program and emits the canonical byte representation for persisted or transmitted replay state.

The v1 canonical JSON byte contract is:

- UTF-8 bytes,
- no BOM,
- no trailing newline,
- no insignificant whitespace,
- JSON object keys sorted lexicographically at every object level,
- JSON array order preserved exactly,
- integer values emitted as ordinary base-10 JSON integers,
- no provider/model state and no alternate binary representation.

Because v1 accepts only exact integers for numeric fields and fixed ASCII schema/operation strings, this restricted canonical surface avoids floating-point and Unicode-normalization ambiguity. `operations`, `pixels`, and duplicate-coordinate order remain untouched because those arrays are semantically significant.

`serialize_pixel_program` does not mutate, reorder, deduplicate or normalize the caller's Python object. Key sorting affects only emitted JSON object-key order. The returned `bytes` object is the canonical replay payload.

`tracepixel.model.deserialize_pixel_program(payload)` accepts UTF-8 JSON `bytes`, decodes them with the Python standard library, and then runs the same P2-IR1 semantic validator. A valid but non-canonical JSON spelling is accepted on input; reserializing the decoded program produces the one canonical byte spelling. Malformed wire input raises `PixelProgramSerializationError` with stable code `invalid_type` or `invalid_json`; semantically invalid decoded documents continue to raise `PixelProgramValidationError`.

IR3 round-trip/replay invariants are:

```text
canonical = serialize_pixel_program(program)
decoded = deserialize_pixel_program(canonical)
serialize_pixel_program(decoded) == canonical
execute_pixel_program(decoded).rgba_bytes() == execute_pixel_program(program).rgba_bytes()
```

Tests additionally pin the exact canonical bytes for an ordered/duplicate-containing fixture and prove that different Python dict insertion order does not alter canonical output. Serialization/deserialization remains dependency-free and provider-free.

## Remaining P2 boundary

The following remains deliberately deferred:

- **P2-IR4:** operation-vocabulary expansion/reduction and compactness/token-proxy/invalidity evidence.

The JSON Schema remains the serialized structural contract. P2-IR1 runtime validation is the semantic authority for cross-field canvas bounds and exact P1 numeric rules. P2-IR2 executes validated in-memory data through P1 raster authority. P2-IR3 defines one deterministic emitted byte spelling and round-trip replay path; it does not broaden the operation vocabulary.

## Versioning rule

A serialized program always carries an explicit schema identity. Incompatible changes to required fields, field meaning or supported operation shape require a new schema identity; they must not silently reinterpret an existing `tracepixel.pixel-program.v1` document.

The canonical JSON byte contract above is part of the supported v1 serialization behavior. A future incompatible byte-level rule must be introduced intentionally rather than silently changing the output of `serialize_pixel_program` for the same valid v1 program.
