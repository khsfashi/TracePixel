# AGENTS.md

This repository is designed to be continued by fresh AI agents without hidden chat context.

## Authority order

When sources disagree, use this order:

1. live GitHub issue / pull request / required-check state,
2. `config/tracepixel.core-lane.json`,
3. `PROJECT_STATUS.md`,
4. active-stage contracts under `docs/`,
5. roadmap prose and older comments.

Never invent completion because a document says a stage is done while live implementation or required checks disagree.

## Continuation rule

For requests equivalent to `TracePixel next` / `다음 작업 진행해줘`:

1. resolve live repository state,
2. identify the single active core-lane item,
3. continue an existing implementation PR before opening new scope,
4. research uncertain external facts before freezing a contract,
5. implement the smallest vertical slice that satisfies the active acceptance criteria,
6. run relevant deterministic checks,
7. update status/handoff evidence,
8. stop at an owner-review state rather than silently approving or launching another provider run,
9. do not jump ahead unless the owner explicitly changes the lane.

Only one core-lane implementation item should be active at a time.

## Post-G8 product rule — PIVOT

Owner decision recorded 2026-08-18: **PIVOT**.

TracePixel is now generator-neutral quality/control infrastructure with optional direct authoring, not a product whose value depends on its staged/direct generator beating every external or RAW generator.

Preferred product boundary:

```text
replaceable generator / RAW / retained external candidate
 -> candidate import / authoritative Canvas
 -> deterministic QA + normalization
 -> bounded local repair where useful
 -> owner perceptual review
 -> exact replay / evidence / telemetry
```

The existing direct/PixelProgram generation path remains available as:

- an optional backend/control,
- a small/simple-asset path where evidence supports it,
- a precision local-repair path.

Do not privilege it merely because TracePixel owns it.

Do not respond to an aesthetic failure by adding humanoid schemas, skeleton/IK/physics, new PixelProgram operations, new schedulers or another direct-generation abstraction unless a frozen workload proves that exact change is the smallest evidence-backed bottleneck fix and the active lane permits it.

Detailed authority: `docs/P11_GENERATOR_NEUTRAL_PIVOT.md`.

## Deterministic versus perceptual authority

- AI/generator/provider execution may be nondeterministic; provider/model state is provenance, never canonical asset truth.
- Deterministic code owns exact pixel mutation and exact measurable facts once a concrete candidate enters TracePixel.
- Exact structural facts must not be delegated to a VLM: dimensions, palette membership, alpha state, bounds, connected components, explicit symmetry/tiling/frame metadata, operation validity and similar facts are deterministic.
- Readability, anatomy, identity, hierarchy, material perception, motion quality, pixel-cluster craft, style and taste remain perceptual/human unless a narrower objective fact is separately frozen.
- Human approval is final for aesthetic/product acceptance.
- Deterministic QA green never means aesthetic PASS.
- A future VLM may be bounded secondary evidence only if G4 is explicitly approved; it never silently becomes final truth.

## Owner-run / self-feedback protocol

Provider-backed promotion/scored experiments must freeze task, backends, budgets, retry limits, deterministic checks, human review criteria and artifact retention **before** the provider call.

Required state machine:

```text
frozen-experiment
 -> owner-triggered-run
 -> awaiting-owner-review
 -> accepted | repair-requested | rejected-stop
```

If the state is `awaiting-owner-review`:

1. do not make another provider call,
2. surface the exact run/candidate identity,
3. surface native and enlarged preview artifacts,
4. report deterministic QA separately from cost/telemetry,
5. show the frozen human review criteria,
6. ask the owner for judgment.

The owner may answer in natural language. Example:

```text
REJECT. silhouette는 괜찮은데 anatomy와 장비 부착이 별로고 재질도 안 읽힌다.
```

Convert owner feedback conservatively into existing P7 feedback/human-review contracts where they fit.

- Bind feedback to the exact reviewed artifact/run/digest.
- Do not infer an unstated criterion failure or success.
- Do not invent region/stage hints.
- If only overall REJECT is given, unspecified criteria remain unresolved.
- Automation must never rewrite an owner REJECT as PASS because deterministic QA is green.

A rejected result is retained evidence. Do not overwrite it with a later preferred output.

### Retry / repair budget

Do not implement `while aesthetic_score < threshold: regenerate()`.

- Cheap deterministic QA/normalization may repeat without provider calls when exact and bounded.
- Provider repair/regeneration occurs only when the frozen experiment permits it.
- First preference after explicit owner feedback is bounded local repair when that can preserve unaffected pixels.
- Full regeneration is a separate budgeted action, not the default definition of repair.
- Never increase provider/token budget merely to chase owner approval after the result is known.

## Benchmark integrity

Benchmark claims must be preregistered before scored runs.

- Pin model/provider/tool versions and prompts/configuration where possible.
- Preserve scored artifacts and raw evidence.
- Do not repair, replace or rerun a frozen scored cohort until it wins.
- Separate development fixtures from held-out scored tasks.
- Report unsuccessful runs, including budget/time/tool failures.
- Measure Agent complexity, not only image quality.
- Keep human-visible quality and cost as separate result layers; do not hide trade-offs in one composite winner score.
- Compare the direct backend honestly against RAW/external alternatives whenever its product value is the claim under test.

Required complexity evidence includes at least input/output tokens when available, provider/tool calls, visual calls, iterations, wall time, human interventions and success/failure category.

## Reuse before invention

P11 and later work should reuse existing seams before introducing a new authority:

- P1 Canvas/RGBA authority,
- P2 PixelProgram/exact replay,
- P4 deterministic QA,
- P7 feedback localization/minimal repair/human feedback,
- P6/P8 review-package patterns,
- existing provider/complexity telemetry.

External generators such as PerfectPixel and sprite-gen are references or candidate backends, not code to clone automatically. Any vendoring/runtime dependency/integration still requires current license/version/architecture review and an active-lane need.

## Performance and ownership

Heavy generation, analysis, VLM calls and preview work are offline/setup operations.

- Avoid unnecessary decoded-image copies and per-pixel Python object graphs.
- Prefer compact contiguous buffers and palette indices where appropriate.
- Reuse/capacity-cache temporary buffers when representative measurements justify it.
- Keep stage/repair snapshots explicit; do not retain every intermediate buffer indefinitely by accident.
- Optimization claims require measured workloads.
- Normal runtime/frame-loop concerns belong to consumer engines such as Trace2D, not TracePixel's offline quality path.

## Public-repository runner safety

The repository is public.

- Normal `pull_request` CI uses GitHub-hosted runners only.
- Never attach an unrestricted home-machine self-hosted runner to automatic public PR execution.
- The owner Windows runner is manually/owner triggered, secret-minimal and isolated from untrusted fork PR execution.
- Paid/model-provider calls must never be mandatory for portable CI.
- An owner-triggered run may use the already-approved trusted ChatGPT/Codex boundary only when the active frozen experiment permits it.

## Change discipline

- Keep core contracts text/diff friendly.
- Prefer standard library and small proven dependencies; add dependencies only when they buy concrete capability.
- Do not proliferate tools merely to help one benchmark case. Reduce the concepts an agent must understand.
- Add high-level operations only after workloads prove they reduce complexity without hiding important authority.
- Preserve deterministic replay from a concrete Pixel IR/program to identical output bytes where the encoder contract allows it.
- A provider-neutral candidate import path must converge on the same downstream authority instead of creating one raster truth per generator.
