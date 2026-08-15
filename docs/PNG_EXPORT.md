# Deterministic PNG Export Contract

Status: **P1-R2 implementation contract**.

TracePixel keeps exact authoritative RGBA8 bytes as replay truth. PNG is a derived artifact, but P1-R2 intentionally controls the encoder tightly enough that encoder-v1 PNG bytes are deterministic for the same source bytes and export parameters.

## Encoder identity

```text
tracepixel.png.rgba8.store.v1
```

The encoder is implemented with the Python standard library only. No Pillow, libpng wrapper or other image stack is added.

The exact PNG layout is:

- PNG signature,
- one `IHDR` chunk,
- one `IDAT` chunk,
- one `IEND` chunk,
- 8-bit RGBA / PNG color type 6,
- no interlacing,
- filter type 0 (`None`) for every scanline,
- zlib wrapper with RFC 1951 stored/uncompressed DEFLATE blocks,
- deterministic block size/order and checksums.

Because compressed search heuristics are not used, encoder-v1 output does not depend on a zlib compressor choosing different block/strategy decisions. `zlib.adler32` is used only for the fixed checksum algorithm.

Changing any byte-producing rule requires a new encoder identity and corresponding golden-byte evidence rather than silently changing encoder-v1 output.

## Native export

`export_native_png(canvas)` emits the canvas at exact native dimensions.

- source pixel order is the canonical row-major RGBA8 authority,
- straight alpha bytes are preserved exactly,
- transparent RGB bytes are preserved,
- no color-space conversion, quantization or resampling occurs.

## Nearest-neighbor preview

`export_nearest_preview_png(canvas, scale)` emits an integer enlarged preview.

- `scale` must be an exact integer `>= 2`,
- each source pixel is replicated exactly `scale x scale`,
- there is no interpolation or antialiasing,
- the enlarged raster reuses the P1 canvas safety ceiling through `CanvasSpec` validation,
- the source canvas is never mutated.

The implementation expands one source row at a time instead of materializing a second full enlarged authoritative canvas.

## Metadata

Every returned `PngExport` carries `PngExportMetadata` with:

- schema and export kind,
- source and output dimensions,
- integer scale,
- pixel/alpha semantics,
- explicit resampling/filter/compression modes,
- encoder identity,
- SHA-256 of the authoritative source RGBA8 bytes,
- SHA-256 of the encoded PNG bytes.

The source RGBA digest remains the stronger semantic replay evidence. The PNG digest proves exact encoder-v1 artifact identity.

## Copy and allocation boundary

P1-R2 deliberately keeps the source read path zero-copy during encoding through a borrowed read-only `memoryview`.

Expected export allocations are:

- explicit `Canvas.rgba_bytes()` only when a caller requests an owned authoritative snapshot,
- one enlarged row buffer for nearest-neighbor preview,
- at most one pending stored-DEFLATE block plus encoder output,
- the final immutable PNG bytes returned to the caller.

P1-R4 will measure representative 16x16, 32x32 and 64x64 allocation/timing evidence before any additional pooling or caching is introduced.

## Determinism evidence

Tests must verify at minimum:

- native PNG decodes to exact authoritative RGBA8 bytes,
- transparent RGB survives round-trip,
- chunk CRCs are valid,
- every scanline uses filter 0,
- same encoder-v1 input produces identical PNG bytes,
- one fixed fixture has a committed golden PNG SHA-256,
- nearest-neighbor preview replicates exact pixels without antialiasing,
- invalid preview scales fail before export.
