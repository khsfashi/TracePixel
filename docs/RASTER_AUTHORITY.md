# Raster Authority Contract

Status: **P1-R0 frozen baseline**.

This contract defines the deterministic pixel authority that P1-R1 and later raster work must implement. It intentionally freezes storage and failure semantics before broad mutation/export code exists.

## 1. Coordinate system

Canvas coordinates are exact Python integers.

```text
origin: top-left
+x: right
+y: down
valid x: [0, width)
valid y: [0, height)
```

No API may silently clip, wrap, round or coerce an out-of-bounds/non-integer coordinate.

`bool` is rejected even though Python treats it as an `int` subclass. Float/string numeric coercion is also rejected.

## 2. Canvas bounds and allocation ceiling

A canvas must have positive integer width/height.

P1 freezes these upper bounds:

```text
max dimension per axis: 4096
bytes per pixel: 4
max pixels: 16,777,216
max authoritative RGBA bytes: 67,108,864 (64 MiB)
```

Validation happens before authoritative allocation.

Python integers do not overflow on multiplication, but adapters/native implementations must preserve the same checked-boundary semantics before allocation or index arithmetic.

These are safety/product bounds, not a statement that 4096x4096 is a representative TracePixel workload. P1-R4 measures the actual small-asset workload separately.

## 3. Canonical pixel representation

The sole canonical raster store is one contiguous row-major RGBA8 byte buffer.

For pixel `(x, y)`:

```text
pixel_index = y * width + x
byte_offset = pixel_index * 4
bytes = [R, G, B, A]
```

P1-R1 should use a mutable contiguous byte-oriented representation such as `bytearray` as its owned authority.

Do not maintain a second canonical pixel store. Views, hashes, encoded images, palettes and previews are derived representations/evidence.

### Palette relationship

Palettes remain important for Agent compactness and art constraints, but palette indices are **not** canonical pixel authority in the P1 baseline.

A future palette/index representation may be:

- an input/IR compression mechanism,
- a validation constraint,
- an export/view optimization,
- a derived mapping over canonical RGBA8.

Replacing canonical RGBA8 with indexed authority, or maintaining competing canonical stores, reopens owner gate G1.

## 4. RGBA8 semantics

Each channel is an exact integer in `[0, 255]`.

RGBA is straight/unassociated alpha. TracePixel does not premultiply authoritative RGB values by alpha.

No implicit color-space conversion, gamma transform, quantization or channel saturation occurs during raster mutation.

Fully transparent pixels preserve their exact RGB bytes. `(255, 0, 0, 0)` and `(0, 0, 0, 0)` are therefore different authoritative pixel values even if a renderer displays both as transparent.

This keeps replay and structural evidence byte-exact and avoids hidden normalization.

## 5. Mutation and transaction semantics

P1-R1 mutation follows these rules:

### Single pixel

1. Validate coordinate.
2. Validate RGBA8.
3. Mutate exactly four authoritative bytes.

A validation failure performs no mutation.

### Batch pixel mutation

A batch is an ordered sequence of edits.

1. Validate the complete batch shape.
2. Validate every coordinate.
3. Validate every RGBA8 value.
4. Only after all validation succeeds, apply edits in input order.

If any edit is invalid, the authoritative buffer remains byte-for-byte unchanged.

Duplicate coordinates are valid. Later edits in the same validated batch win deterministically.

The implementation may choose an efficient validation/application strategy, but it must preserve all-or-nothing authoritative semantics and must not build a permanent object-per-pixel graph.

## 6. Error semantics

Raster contract violations use explicit deterministic errors rooted at `RasterContractError`.

Current categories:

- `CanvasSizeError` — invalid dimensions/allocation bound,
- `PixelCoordinateError` — invalid or out-of-bounds coordinate,
- `ColorValueError` — invalid RGBA8 value.

Public APIs must not rely on incidental `bytearray`, `IndexError` or coercion behavior as their contract.

Later IR validation may translate these into higher-level typed findings without changing raster authority.

## 7. Deterministic evidence boundary

The strongest raster replay truth is:

```text
(width, height, exact authoritative RGBA bytes)
```

For the same validated concrete program/input, P1 must reproduce identical authoritative RGBA bytes and structural metadata.

Encoded PNG bytes are not automatically canonical truth. PNG container/chunk/compression bytes may vary across encoders or configuration even when decoded pixels are identical.

P1-R2 may claim PNG byte identity only if the encoder and configuration are explicitly controlled and tested. Otherwise PNG is an export artifact while authoritative RGBA bytes remain the replay authority.

Nearest-neighbor enlarged previews are always derived evidence and never feed back into canonical pixels.

## 8. Copy/allocation policy

The baseline architecture is intentionally copy-conscious:

- one owned contiguous authoritative buffer,
- no object per pixel in steady-state storage,
- no implicit full-canvas copy for ordinary read/write,
- explicit copies only when ownership/evidence/export requires them,
- temporary batch-validation storage should be bounded to the operation and measured at P1-R4.

Do not add buffer pooling/caching merely because it may help. P1-R4 should first measure representative 16x16, 32x32 and 64x64 workloads; optimize/capacity-cache where evidence justifies it.

## 9. P1-R0 acceptance

P1-R0 is complete when main contains:

- this written authority contract,
- executable `CanvasSpec` validation/layout metadata,
- tests for coordinate/layout/bounds/RGBA8 invariants,
- architecture prose aligned to a single contiguous RGBA8 authority,
- no Canvas mutation implementation yet,
- no image/PNG dependency,
- continuation advanced to P1-R1 only after CI is green.

P1-R1 may implement the canvas and transactional mutation against this contract without reopening G1 unless it proposes materially different canonical storage semantics.
