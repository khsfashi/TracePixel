# Pixel IR Contract

P2-IR0 freezes the first public serialized `PixelProgram` boundary without introducing provider/model state, execution semantics or a second pixel authority.

## Authority

The v1 serialized document is JSON-compatible data identified by:

```text
tracepixel.pixel-program.v1
```

The machine-readable structural contract is `schemas/pixel-program.v1.schema.json`. Python `TypedDict` declarations in `tracepixel.model` mirror that shape for library/tooling ergonomics; Python source code, callables and provider SDK objects are not canonical program state.

A concrete program is intended to flow into later deterministic validation/execution and then the existing P1 `Canvas` authority:

```text
PixelProgram(v1)
 -> P2-IR1 validation
 -> P2-IR2 deterministic executor
 -> Canvas / authoritative RGBA8
```

`ArtIntent` and `StagePlan` remain architectural upstream concepts, but P2-IR0 does not freeze their serialized shape. Stage semantics belong to P3 and should not leak into the minimal replay program early.

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

This representation is intentionally close to the P1 transactional batch authority while avoiding one verbose object/key set per pixel. `operations` order and each `pixels` array order are explicit serialized order; later validation/execution must preserve deterministic ordering and the P1 duplicate-coordinate last-write-wins contract.

`set_pixels` alone can express any finite RGBA raster, so P2 does not need to guess line/rect/fill/art-aware operations before the P2-IR4 compactness evidence. Additional operation kinds require an intentional schema/version decision rather than an open-ended command bag.

## What P2-IR0 does not define

P2-IR0 is structural only. The following remain deliberately deferred:

- **P2-IR1:** exact rejection rules, numeric ranges, canvas bounds, unknown/unsupported-version behavior and semantic validation,
- **P2-IR2:** transactional deterministic execution through P1 `Canvas`,
- **P2-IR3:** canonical JSON serialization/order and replay round-trip evidence,
- **P2-IR4:** operation-vocabulary expansion/reduction and compactness/token-proxy evidence.

The JSON Schema therefore freezes document shape and discriminators but does not duplicate all P1 numeric/bounds semantics yet.

## Versioning rule

A serialized program always carries an explicit schema identity. Incompatible changes to required fields, field meaning or supported operation shape require a new schema identity; they must not silently reinterpret an existing `tracepixel.pixel-program.v1` document.

Canonical byte serialization is not claimed in IR0. That contract belongs to P2-IR3.
