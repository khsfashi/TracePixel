# P1-R4 Raster Memory / Performance Evidence

P1-R4 is an **engineering checkpoint**, not a portable benchmark claim. It records two different kinds of evidence and deliberately keeps them separate.

## 1. Environment-independent structural evidence

`structural.json` is committed and golden-tested. It records exact payload/copy facts for 16×16, 32×32 and 64×64 canvases under the current P1 contracts.

| Canvas | Authority RGBA | Transaction staging | Explicit RGBA snapshot | Native PNG | 2× preview raster | Reused preview row | 2× preview PNG |
|---|---:|---:|---:|---:|---:|---:|---:|
| 16×16 | 1,024 B | 2,048 B | 1,024 B | 1,108 B | 4,096 B | 128 B | 4,196 B |
| 32×32 | 4,096 B | 8,192 B | 4,096 B | 4,196 B | 16,384 B | 256 B | 16,516 B |
| 64×64 | 16,384 B | 32,768 B | 16,384 B | 16,516 B | 65,536 B | 512 B | 65,737 B |

Interpretation:

- authoritative steady storage is exactly `width * height * 4` bytes of RGBA payload,
- transactional `set_pixels()` validates into one compact fixed 8-byte record per edit before any authoritative write; a full-canvas one-edit-per-pixel batch therefore stages exactly 2× the authoritative pixel payload,
- `Canvas.rgba_bytes()` creates one full owned snapshot only when explicitly requested,
- native export borrows a read-only view of authoritative bytes rather than first copying the source canvas,
- enlarged preview never materializes a second full preview canvas; it reuses one scaled row buffer,
- the returned native/preview PNG byte strings are derived owned output and therefore unavoidable when that export is requested.

The first P1-R4 CI sample exposed the reason to compact transaction staging: on CPython 3.13.15 / GitHub-hosted Ubuntu, the previous three-list Python-object staging path reached 785,800 traced peak extra bytes for a 64×64 full-canvas batch while authoritative RGBA payload was only 16,384 bytes. P1-R4 replaced those duplicate staging collections with the fixed packed record buffer while preserving all-or-nothing validation and ordered last-write-wins behavior. This observation is environment-labelled diagnostic evidence, not a cross-machine performance claim.

The JSON payload sizes are correctness evidence for the current contracts and must change intentionally if byte-producing or transaction-staging rules change.

## 2. Environment-labelled runtime evidence

Run from the repository root after installing TracePixel editable:

```bash
python -m evidence.p1_r4.benchmark --iterations 7
```

The collector emits `tracepixel.p1-r4-runtime-evidence.v1` JSON containing:

- Python implementation/version, platform, machine and pointer width,
- `tracemalloc` retained/peak extra bytes for single-pixel mutation, full-canvas transactional batch mutation, explicit snapshot, native export and 2× preview export,
- exact transaction staging payload bytes beside the allocator measurement,
- `perf_counter_ns` min/median/max timing for full replay, native export and 2× preview export at 16×16, 32×32 and 64×64.

Portable CI executes the collector on Python 3.12 and 3.13 so every implementation head records environment-labelled samples in the Actions log.

## Measurement policy

Runtime values are **not** golden files and are **not** pass/fail thresholds. They depend on interpreter build, allocator, host load and hardware. Correctness tests assert only structural contracts/schema/invariants; timings and `tracemalloc` values are diagnostic evidence for architecture decisions.

Do not introduce pooling/caching merely to improve this microbenchmark. A later optimization should first identify a real workload problem, preserve deterministic authority, and then compare equivalent before/after evidence.
