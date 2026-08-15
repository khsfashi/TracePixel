# Project Status

Last explanatory handoff update: **2026-08-15**

This file is context. Live GitHub state and `config/tracepixel.core-lane.json` are operational authority.

## Product rule

> Humans define intent and judge the result. AI owns the iteration in between.

> Deterministic where possible. Multimodal where necessary. Human judgment at the end.

TracePixel is an independent research/production-tool project for agent-authored, deterministic small pixel assets. It should prove its value by benchmark before any Trace2D integration claim.

## P0 foundation — complete

P0 merged via PR #1 / squash `5626a11dbd9bc7dbe7459f5d088ffdd2bb11c6f2`.

Delivered:

- product and Agent authority contracts,
- preregistered benchmark methodology,
- reference-project/research register,
- machine-readable continuation lane,
- dependency-free Python 3.12+ package skeleton,
- compact deterministic `tracepixel doctor` command,
- GitHub-hosted CI on Python 3.12 and 3.13,
- public-repository safety rule excluding automatic untrusted PR execution on a future home self-hosted runner.

Owner CI run #1 passed on both Python 3.12 and 3.13 before merge.

## Roadmap hardening

The project keeps the original P1-P9 sequence, but each phase has a fixed child lane in `docs/ROADMAP.md` and `config/tracepixel.core-lane.json`.

Cross-cutting additions:

- explicit child-lane acceptance/stop boundaries,
- pre-B0 engineering checkpoints,
- incremental preview milestones,
- explicit owner decision gates in `docs/DECISION_GATES.md`,
- scored B0/B1 freeze/postmortem rules that preserve unsuccessful runs.

The purpose is to let future `TracePixel next/continue` work proceed autonomously on reversible engineering details while stopping before product/scope decisions that require owner judgment.

## P1-R0 raster authority — complete

P1-R0 froze the baseline that later raster code must preserve:

- top-left origin, zero-based half-open integer coordinates,
- one contiguous row-major RGBA8 canonical pixel store,
- exact straight/unpremultiplied alpha bytes with transparent RGB preserved,
- palette/index data is derived or authoring metadata rather than competing pixel authority,
- 4096 per-axis safety ceiling / 64 MiB maximum authoritative RGBA allocation,
- explicit raster contract error categories,
- all-or-nothing ordered batch mutation semantics with deterministic last-write-wins duplicates,
- authoritative replay truth is dimensions plus exact RGBA bytes; PNG bytes are export evidence unless an encoder contract later proves byte identity.

Executable layout/bounds/color validation lives in `tracepixel.raster.CanvasSpec` and `docs/RASTER_AUTHORITY.md` is the written authority.

## P1-R1 canvas + transactional mutation — complete

PR #6 implements the frozen R0 authority without reopening G1:

- one owned contiguous `bytearray` backing store,
- deterministic transparent-black initial state,
- exact `get_pixel` and `set_pixel`,
- ordered `set_pixels` transactional batch mutation,
- full batch shape/coordinate/color validation before authoritative writes,
- invalid batches leave authoritative pixels unchanged,
- duplicate coordinates resolve by deterministic last-write-wins order,
- no PNG/image dependency, semantic drawing primitive, provider call or second canonical pixel store.

PR #6 passed GitHub-hosted CI on Python 3.12 and 3.13 before merge.

## P1-R2 deterministic export — complete

PR #7 implements deterministic export without opening G2:

- exact native-size RGBA8 PNG export,
- integer nearest-neighbor enlarged preview with no interpolation or antialiasing,
- explicit `tracepixel.png-export.v1` metadata including source/output dimensions and SHA-256 evidence,
- controlled encoder identity `tracepixel.png.rgba8.store.v1`,
- fixed PNG filter 0 plus stored DEFLATE blocks so encoder-v1 byte output is deterministic and golden-tested,
- exact authoritative RGBA bytes remain the stronger semantic replay truth,
- public `Canvas.rgba_bytes()` provides an explicit owned snapshot while synchronous package export reads the source through a read-only zero-copy view,
- enlarged preview materializes one scaled row at a time rather than a second authoritative canvas,
- no Pillow/libpng wrapper, provider, GPU requirement or new semantic drawing operation.

PR #7 passed GitHub-hosted CI on Python 3.12 and 3.13 before merge.

## P1-R3 replay fixture + first visible preview — complete

PR #8 freezes the first recognizable human-visible TracePixel replay fixture without advancing P2 scope early:

- a 16x16 potion fixture expressed as fixture-local row/palette data,
- replay through only the existing `Canvas.set_pixels()` mutation surface,
- committed 1024-byte authoritative `potion.rgba` golden truth,
- deterministic native 16x16 PNG evidence,
- deterministic 2x / 32x32 nearest-neighbor preview evidence,
- stable `tracepixel.p1-r3-evidence.v1` manifest with fixture/program/output SHA-256 metadata,
- tests that require regenerated authoritative RGBA, native PNG, preview PNG and structural metadata to match committed evidence exactly,
- no provider, VLM, image dependency, semantic drawing primitive, public Pixel IR or second canonical store.

Authoritative RGBA SHA-256 is `bcf8159ae4f8eeb1cde880a85a7b18cca66cfc8c5aaef40798a6a445269f2e27`; native PNG SHA-256 is `d0fb6d9e3acd5d426236c20669089c56c2a1a764b6b8c82e8996591e9adc84d9`; 2x preview PNG SHA-256 is `48bb9254824ce6ca2cba96908daedd9b76e460c2b3d7ebeb25449c40e179c20a`.

PR #8 final head `0d084881ff7f9f63afe9f26046b470ab9c24b141` passed GitHub-hosted CI run #19 before merge.

## P1-R4 memory/performance evidence — complete via PR #9

PR #9 records the final P1 engineering checkpoint without turning machine-local timings into correctness claims:

- committed/golden structural evidence at 16x16, 32x32 and 64x64,
- exact authoritative RGBA payloads of 1,024 / 4,096 / 16,384 bytes,
- explicit owned RGBA snapshots of the same payload sizes only when requested,
- deterministic native PNG output payloads of 1,108 / 4,196 / 16,516 bytes,
- 2x preview raster payloads of 4,096 / 16,384 / 65,536 bytes while only one 128 / 256 / 512-byte scaled row buffer is reused,
- 2x preview PNG output payloads of 4,196 / 16,516 / 65,737 bytes,
- environment-labelled `tracemalloc` allocation and `perf_counter_ns` replay/native-export/preview-export evidence in portable CI,
- no runtime timing or allocator value used as a pass/fail performance threshold.

The first P1-R4 CI measurement exposed an avoidable mutation-path cost: CPython 3.13.15 on the GitHub-hosted Ubuntu runner measured 785,800 traced peak extra bytes for a 64x64 full-canvas `set_pixels()` batch while authoritative RGBA payload was 16,384 bytes. The cause was duplicate Python-object staging collections for batch shape, offsets and colors.

PR #9 therefore keeps the same P1 transaction semantics but stages each validated edit as one packed 8-byte `<IBBBB` record (byte offset + RGBA). Full-canvas staging payload is now exactly 2,048 / 8,192 / 32,768 bytes for 16x16 / 32x32 / 64x64. On implementation CI run #26, both CPython 3.12.13 and 3.13.15 measured 33,365 traced peak extra bytes for the 64x64 full-batch path; the CPython 3.13 comparison is a 95.8% peak reduction from the initial environment-labelled sample. Existing rollback and ordered duplicate/last-write-wins tests remain green.

Implementation head `a5920c30e8c494a3d49d06bfe5feba23ce9bf7f1` passed GitHub-hosted CI run #26 on Python 3.12 and 3.13. PR #9 subsequently merged and issue #2 closed as completed.

No provider, VLM, GPU, image dependency, secret or self-hosted runner was introduced in P1.

## P2-IR0 PixelProgram schema — complete after PR #11 merges green

PR #11 freezes the smallest public serialized program boundary needed before runtime validation/execution:

- schema identity `tracepixel.pixel-program.v1`,
- a closed top-level `schema` / `canvas` / ordered `operations` envelope,
- a dependency-free JSON Schema structural authority at `schemas/pixel-program.v1.schema.json`,
- provider-neutral `TypedDict` mirrors under `tracepixel.model` for library/tooling ergonomics,
- one initial exact `set_pixels` operation,
- compact ordered pixel edits encoded as `[x, y, r, g, b, a]`,
- no unbounded metadata/extensions bag inside canonical replay data,
- no serialized `ArtIntent` or `StagePlan` contract yet; staged-authoring semantics remain deferred to P3,
- no runtime validation, execution, canonical JSON serialization or operation-vocabulary expansion pulled forward from IR1-IR4.

`set_pixels` can express any finite RGBA raster, so IR0 does not guess geometric or art-aware convenience operations before the P2-IR4 compactness evidence. The schema preserves explicit operation/edit ordering and is designed to map into the existing P1 transactional raster authority once IR1/IR2 are implemented.

Implementation head `06e5fa34adbcb7635f203b558dfaba18491e6115` passed GitHub-hosted CI run #30 on Python 3.12 and 3.13. The final handoff head must also be green before PR #11 merges.

No provider/model dependency, VLM, GPU requirement, image dependency, secret, self-hosted runner or new pixel authority was introduced.

## Current core lane

P2 — Versioned Pixel IR and bounded operation vocabulary / issue #10 remains the active phase.

Exact current child after PR #11 merges green:

```text
P2-IR1 validation
```

`config/tracepixel.core-lane.json` advances to `P2-IR1` in the PR #11 handoff. IR1 should validate the frozen v1 structure and finite semantic constraints before any raster mutation, including supported schema/op identity, canvas dimensions, edit tuple shape, coordinates and RGBA8 ranges. Invalid programs must fail before authoritative mutation. Runtime execution itself remains P2-IR2.

Do not jump to deterministic execution, canonical serialization, operation-vocabulary expansion, staged authoring, Agent/provider integration, Aseprite/MCP, VLM review or the home Windows runner while the earlier P2 child remains active.

## Early engineering checkpoints

Before the scored B0 cohort:

```text
P1-R4 raster memory/copy evidence — complete
P2-IR4 IR compactness/replay/invalidity evidence
P4-Q5 seeded deterministic QA coverage
P5-A5 non-scored Agent complexity pilot
```

These are architecture diagnostics, not held-out product claims. They may change later implementation before B0 is frozen.

## Preview direction

Human visibility is incremental:

```text
P1-R3 -> native PNG + enlarged nearest preview — complete
P3-S7 -> stage-by-stage preview evidence
P4-Q5 -> preview + deterministic QA findings
P5-A5 -> first opt-in AI-authored raster preview
P6-V5 -> mobile static gallery/review flow
```

A home Windows PC may later act as an owner-triggered preview runner at P6-V6. It is not part of normal public-PR CI and requires explicit owner approval before connection.

## Owner decision gates

`docs/DECISION_GATES.md` is authoritative for questions autonomous continuation must not silently resolve.

Important future gates include:

- materially changing the canonical pixel representation,
- adding a substantial image/PNG dependency,
- choosing the first real provider/model,
- using a VLM as secondary perceptual evidence,
- including Aseprite/MCP as a scored baseline,
- connecting the home self-hosted runner,
- promoting humanoids or animation into scope,
- starting the Trace2D adapter experiment.

If an existing recorded owner decision already answers the exact gate, do not ask again unless materially new evidence invalidates it.

## Benchmark direction

B0 is development-visible architecture evidence, not a final marketing claim. One exact preregistration commit must freeze tasks, baselines, provider/model settings, budgets, scoring, retry/exclusion policy and retention rules before scoring.

B0 remains immutable after scoring. B1 begins only after B0-driven changes are implemented and uses held-out frozen variants.

## Trace2D boundary

TracePixel does not modify Trace2D's runtime architecture. A future adapter may expose successful generation results as provider-neutral RGBA/metadata/manifests that can enter Trace2D's existing Sprite/Asset Intelligence preparation paths.

P9 does not begin automatically from positive benchmark results: it additionally requires explicit owner approval and its own matched integration benchmark.

## Continuation rule

The next `@GitHub TracePixel 다음 작업 진행해줘` must resolve live state first.

- If issue #10 has an implementation PR, continue/fix that PR until its exact-head checks are green and the active P2 child is complete.
- If issue #10 is open with no implementation PR, begin the `current_child` from `config/tracepixel.core-lane.json` only.
- Advance through `P2-IR0 -> IR1 -> IR2 -> IR3 -> IR4` in order unless an explicit owner decision changes the contract.
- Stop at unresolved owner gates rather than guessing.
- Live GitHub state wins over stale prose.
