# P7-F0 Feedback / Finding Intake

P7-F0 defines the bounded input boundary for targeted repair. It does **not** localize an affected region, create a repair PixelProgram, re-run the asset, or decide that an image is perceptually good.

## Contract

`tracepixel.feedback-intake.v1` binds feedback to one logical target:

- `asset_id` and `task_id` preserve logical identity.
- `canvas` makes region hints checkable without loading raster bytes.
- optional `artifact_sha256` binds intake to exact pre-repair bytes when available.
- `items` is closed and bounded to 1..32 entries.

Each item has a stable `id`, bounded `source_ref` and `summary`, plus optional `stage_hint` and `region_hint`.

## Authority separation

Two authorities are intentionally disjoint:

### `deterministic_qa`

A deterministic item must carry exactly one existing TracePixel QA rule/category/severity triple. Its `human` payload must be null. Rule/category consistency is validated.

The free-form `summary` is explanatory only; it cannot add a new deterministic rule or change the recorded QA category/severity.

### `owner_human`

A human item must have `deterministic_qa = null`. It may retain owner rejection and the already-established 1..5 review dimensions (`recognizability`, `native_1x_readability`, `style_coherence`), or carry bounded prose with no score.

Human evidence remains human evidence. A rejection, low score, or subjective summary is never converted to `all_rules_pass = false` or another deterministic QA result.

## Hints are not localization

`stage_hint` is limited to the existing P3 stage IDs. `region_hint` is a top-left, half-open rectangle that must fit inside the target canvas.

Both are suggestions supplied by the source. P7-F1 owns the deterministic/reviewable **affected stage/region localization** result. P7-F0 therefore exposes no `affected_region`, `repair_program`, changed-pixel count, or re-execution state.

## Bounds

- feedback items: 1..32
- item id: 1..64 characters
- source ref: 1..128 characters
- summary: 1..512 characters
- owner scores: maximum three unique known dimensions, each exact integer 1..5
- canvas: existing P1 `CanvasSpec` limits
- artifact digest: optional exact lowercase SHA-256

## B0 boundary

P7 may consume lessons or retained references from immutable B0 evidence, but this contract does not rewrite B0 ratings, deterministic scores, artifacts, or attempt manifests. P7 changes are evaluated later under the separately frozen B1 cohort.

## Handoff

After P7-F0 is accepted, P7-F1 may map each validated item to an explicit affected stage/region while preserving the original authority and source evidence unchanged.
