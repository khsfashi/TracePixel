# B0 preregistration freeze

B0 is a **development-visible architecture diagnostic**, not a final marketing benchmark.

The machine-readable authority for the initial B0 cohort is:

- `evidence/b0/preregistration.v1.json`
- schema: `tracepixel.b0-preregistration.v1`

The authoritative freeze commit used by scored results is the commit on `main` that first contains this exact manifest after the B0-F0 PR is merged. The active B0 issue must record that `main` commit before any scored attempt starts.

## What is frozen

B0-v1 freezes all information required by `docs/BENCHMARK.md` before scoring:

- seven development-visible tasks spanning T0 through T3,
- the exact visible prompt text for every task,
- hidden deterministic verifier constraints,
- two scored methods,
- provider/model/tool versions and settings,
- trial count and finite Agent/provider budgets,
- retry and exclusion policy,
- deterministic aggregation,
- complexity reporting,
- blind owner perceptual review,
- human-intervention policy,
- failure taxonomy,
- artifact retention and immutability rules.

No scored run may begin during B0-F0.

## Scored comparison

The initial cohort deliberately keeps the comparison narrow and matched:

1. `tracepixel-staged-v1`
   - current TracePixel staged Agent surface,
   - ArtIntent/stage-aware compact observation,
   - bounded PixelProgram proposals,
   - deterministic execution and QA.

2. `raw-pixel-program-v1`
   - same Codex CLI/provider/model,
   - same visible task information,
   - no TracePixel stage guidance,
   - only the low-level v1 `set_pixels` PixelProgram surface plus matched deterministic QA feedback.

This directly tests whether the staged Agent-facing architecture adds value over the lower-level primitive surface without changing the model family or giving one method extra task information.

## Frozen real-provider boundary

B0 reuses the already-resolved G3 boundary from P5-A5:

- provider surface: OpenAI Codex CLI,
- auth: ChatGPT,
- model: `gpt-5.6-sol`,
- reasoning effort: `low`,
- Codex CLI: `0.147.0`,
- vision input: off,
- read-only sandbox,
- ephemeral execution,
- no separately metered API-key billing.

Portable CI remains provider/network free. Scored provider runs are owner-triggered local/headless work and do not enable a GitHub self-hosted runner.

## Gates intentionally not crossed

### G4 — VLM/perceptual judge

Unresolved. B0-v1 therefore has **no VLM judge**. Perception is recorded only by the frozen blind human review procedure and never overrides deterministic structural facts.

### G5 — Aseprite/MCP scored baseline

Unresolved. Aseprite/MCP is explicitly **not scored** in this cohort.

### G6 — home Windows self-hosted runner

Unresolved. B0-v1 uses owner-triggered local/headless execution, not an attached GitHub self-hosted runner.

## Cohort size

The frozen cohort contains:

- 7 tasks,
- 2 scored methods,
- 2 trials per task/method,
- 28 scheduled scored attempts total.

All tasks stay at 16x16. The cumulative pixel-edit budget is 1024 per trial, which permits at most four full-canvas-equivalent edit passes and therefore gives both methods bounded revision headroom without introducing a larger canvas-scale promotion.

## Result layers

B0-v1 never collapses everything into one score. Reports must keep separate:

- completion rate,
- deterministic all-rules structural pass rate,
- mean deterministic rule fraction,
- raw + aggregated Agent complexity telemetry,
- blind human recognizability/readability/style-coherence ratings,
- failure taxonomy and postmortem.

A visually attractive but structurally invalid artifact therefore remains distinguishable from a structurally valid but aesthetically weak one.

## Retry and failure integrity

There is no semantic reroll after a valid provider response. One identical-request transport retry is allowed only when no usable proposal bytes were returned, and it consumes the same trial budget.

After provider invocation, failed attempts are never excluded. Budget, timeout, provider, invalid IR, verifier, semantic and human failures remain in the result set. A pre-invocation harness defect may be rerun once only under the explicit `void_infrastructure` rule while retaining the original record and citing the fix commit.

## Retention

Every scheduled attempt is retained, including failures. Scored evidence must include the request/response, proposal or failure record, deterministic QA, telemetry and final raster/PNG evidence when produced. Authentication material is never retained.

The result path must cite the authoritative B0-F0 freeze commit on `main`. Once the first scored attempt starts, this B0 cohort cannot be edited, relabelled or rerun to improve TracePixel's result.

## Handoff

After this freeze is merged and required checks are green, advance only to **B0-H0 matched harness**. H0 may implement the common result schema and adapters needed to execute the already-frozen contract, but it may not change the B0-v1 tasks, scored methods, model/settings, budgets, trial count, scoring, retry/exclusion policy or retention rules.
