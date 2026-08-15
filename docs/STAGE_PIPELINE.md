# Stage Pipeline v1

`tracepixel.stage-plan.v1` and `tracepixel.stage-pipeline-evidence.v1` are the P3-S7 contracts that turn the S1-S6 coarse-to-fine sequence into one deterministic executable and replayable pipeline.

P3-S7 does not add a second pixel authority. Every applied stage still owns an ordinary validated `tracepixel.pixel-program.v1`, and those programs are applied in fixed order to one P1 `Canvas`.

## Fixed stage plan

A v1 plan contains exactly six entries in this order:

```text
silhouette
 -> major_forms
 -> palette_light_ramp
 -> shading
 -> semantic_details
 -> outline_cleanup
```

Each entry contains exactly:

```text
stage
document
skip_reason
```

An entry has one of two unambiguous states:

- **applied**: `document` is the matching S1-S6 stage document and `skip_reason` is `null`;
- **skipped**: `document` is `null` and `skip_reason` is a non-blank authored reason of at most 128 characters.

An empty-but-applied stage document remains distinct from a skipped stage. The plan cannot omit, duplicate, reorder, or silently replace a stage with arbitrary Python code.

## Cross-stage validation

`validate_stage_plan(plan, art_intent=...)` validates ArtIntent first, then each applied stage through its existing S1-S6 validator.

S7 additionally enforces the relationships that require the whole sequence to be visible:

- every applied stage PixelProgram targets exactly the ArtIntent canvas;
- the declared S3 palette may not exceed `ArtIntent.composition.palette_budget` when a budget is present;
- applied S4 shading, S5 semantic details, and S6 outline/cleanup require an applied S3 palette/light stage because their color/ramp contracts consume that context;
- skipped stages remain explicit ordered transitions rather than disappearing from evidence.

This boundary does not infer whether an asset is recognizable, attractive, stylistically coherent, or semantically correct.

## One authoritative Canvas

`execute_stage_pipeline()` allocates exactly one authoritative P1 Canvas and applies validated stage-local PixelPrograms to it in S1-S6 order.

The executor does not create a second canonical raster, normalize stage programs, or translate them into a new operation vocabulary. The existing P2 PixelProgram and P1 transactional mutation contracts remain authoritative.

For the already-validated execution path, TracePixel reuses the internal validated PixelProgram application helper so stage edits are not redundantly semantically validated a second time. Authoritative SHA-256 calculation reads the package-internal read-only RGBA view and does not allocate a full raster snapshot only to hash it.

## Transition evidence

Every transition records:

- `stage` and `input_stage` identity;
- `status` and explicit `skip_reason` when skipped;
- input and output authoritative RGBA SHA-256;
- the exact applied PixelProgram and its canonical SHA-256, or `null` for a skip;
- operation count and serialized pixel-edit count;
- `touched_bounds`, the minimal rectangle containing serialized edits;
- optional deterministic nearest-neighbor preview metadata and PNG SHA-256.

`touched_bounds` is repair locality evidence, not a claim that every serialized write changed the previous pixel or that the rectangle has perceptual meaning. The exact PixelProgram remains available for later P7 stage-local repair.

The top-level evidence also records canonical SHA-256 links to the ArtIntent and StagePlan plus the final authoritative RGBA digest.

## Preview snapshots

Preview generation is optional for normal execution so a valid large Canvas is not constrained by an arbitrary enlargement factor.

When a caller supplies `preview_scale >= 2`, S7 exports one deterministic nearest-neighbor PNG after every transition, including skipped transitions. `StagePipelineResult.previews` carries the actual PNG bytes while canonical evidence carries stable metadata and the PNG digest.

The committed `evidence/p3_s7` fixture uses a 2x preview for all six stages so the P3 preview milestone is directly inspectable without a provider, VLM, GPU, image library, or self-hosted runner.

## Provider-free replay

`replay_stage_pipeline_evidence()` starts from the recorded blank canvas, reapplies only recorded PixelPrograms in fixed order, and verifies:

- stage/input-stage ordering;
- input/output digest chaining;
- canonical PixelProgram digests;
- operation/edit counts and touched bounds;
- strict skip records;
- optional deterministic preview metadata/digests;
- final authoritative RGBA digest.

Replay needs no ArtIntent semantics, stage-specific art validator, provider, or model because the evidence already contains the exact P2 replay programs. This keeps the replay boundary compact while the original ArtIntent/StagePlan are linked by canonical hashes.

## Complexity and memory

Let `E` be total serialized edits and `P` the canvas pixel count.

- Plan/stage validation is linear in bounded stage metadata plus `E`.
- Stage application is `O(E)` through the existing P1 mutation path.
- Authoritative digesting is `O(P)` per transition and zero-copy with respect to the canonical RGBA store.
- Optional preview export is `O(P * scale^2)` per transition by definition of the enlarged output and retains only the requested PNG evidence bytes, not a second canonical Canvas.
- Transition locality uses constant scalar min/max state rather than a per-pixel set.

## Scope boundary

P3-S7 does **not** add:

- deterministic aesthetic or recognizability scoring;
- P4 palette/connectivity/shape/tile QA analyzers;
- repair policy or human feedback logic from P7;
- a new PixelProgram operation;
- a provider/model or VLM;
- Pillow, GPU, or other image dependency;
- Aseprite/MCP integration;
- a self-hosted runner.
