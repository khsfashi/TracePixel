# Roadmap

TracePixel is built vertically. Every phase must leave a runnable, testable and documented slice rather than a collection of disconnected AI/art experiments.

## Fixed product direction

TracePixel is an **agent-first deterministic pixel asset authoring and benchmarking toolkit**.

It is not a general illustration generator. The initial product claim is narrower:

> For small constrained game assets, can an AI agent express artistic intent through a compact validated representation, while deterministic tools guarantee exact pixels and machine-verifiable constraints?

Primary judgment split:

```text
objective structural fact -> deterministic code
ambiguous perceptual quality -> optional VLM/multimodal review
final aesthetic acceptance -> human
```

## Fixed high-level sequence

```text
P0 Foundation
 -> P1 Raster Core
 -> P2 Pixel IR
 -> P3 Staged Authoring
 -> P4 Deterministic QA
 -> P5 Agent Loop
 -> P6 Preview/Gallery
 -> B0 Matched Benchmark
 -> P7 Targeted Repair
 -> B1 Held-out Benchmark
 -> P8 Production Breadth
 -> P9 Trace2D Adapter Experiment
```

The high-level sequence is stable. The child lanes below define the ordinary `TracePixel next/continue` order inside each phase. Exactly one child lane should be active unless an explicit owner decision changes the plan.

Benchmarks are deliberately interleaved. TracePixel must not wait until it is feature-complete before testing whether its agent-facing architecture is actually efficient.

## Cross-cutting execution rules

1. Continue an active implementation PR before opening later child scope.
2. Do not advance a child until its acceptance criteria and required checks are green.
3. Run small engineering measurements before the scored B0 cohort where the architecture could otherwise drift blindly.
4. Generated pixels are evidence/output; deterministic canvas/IR/QA contracts remain the machine authority.
5. Perceptual/VLM judgments never silently become deterministic truth.
6. Owner-decision gates in [`DECISION_GATES.md`](DECISION_GATES.md) stop autonomous continuation until resolved.
7. Preview evidence appears incrementally; human visibility is not postponed until the gallery phase.

---

## P0 — Repository and benchmark foundation — complete

Delivered:

- repository/agent authority rules,
- machine-readable continuation lane,
- minimal Python package and doctor command,
- GitHub-hosted portable CI,
- architecture contract,
- benchmark preregistration,
- reference-project register.

No LLM provider dependency was introduced.

---

## P1 — Deterministic raster core

Goal: prove exact replayable pixel authority before any LLM/provider dependency.

Fixed child order:

```text
P1-R0 authority contract
 -> P1-R1 canvas + transactional mutation
 -> P1-R2 deterministic export
 -> P1-R3 replay fixture + preview evidence
 -> P1-R4 memory/performance evidence
```

### P1-R0 — Raster authority contract

Freeze before broad implementation:

- exact integer canvas coordinates and bounds,
- authoritative contiguous pixel representation,
- RGBA8/color/alpha semantics,
- relationship to finite palettes/indexed-color-friendly workflows,
- maximum supported dimensions and overflow validation,
- mutation failure/transaction semantics,
- deterministic-evidence boundary for pixel bytes versus encoded file bytes.

Avoid Python object-per-pixel authoritative storage.

**Owner gate:** if choosing a first-class indexed-palette authority would materially complicate or replace the contiguous RGBA8 baseline, stop for owner review. See `DECISION_GATES.md`.

### P1-R1 — Canvas and transactional mutation

Required minimum:

- create canvas,
- read one pixel,
- set one pixel,
- bounded batch set,
- clear/fill only where justified,
- invalid batch causes no partial mutation,
- ordinary read/write paths do not allocate a per-pixel object graph.

Line/rectangle/flood algorithms stay deferred unless P1 evidence proves they materially simplify the seam without bloating the public API.

### P1-R2 — Deterministic export

Provide:

- native-size PNG,
- nearest-neighbor enlarged preview,
- explicit export metadata,
- no implicit resampling/antialiasing.

Encoded PNG byte identity is claimed only if the chosen encoder/configuration is controlled and tested. Authoritative RGBA bytes remain the stronger replay truth.

**Owner gate:** adding a non-trivial PNG/image dependency requires an explicit dependency decision.

### P1-R3 — Replay fixture and first visible asset

Commit at least one recognizable small non-humanoid fixture such as a potion, key, gem or simple sword/symbol.

Evidence:

- exact authoritative pixel equality,
- same program/input -> same structural metadata,
- native PNG,
- enlarged nearest preview.

**Preview milestone:** from this child onward the owner can inspect an actual TracePixel-generated raster result.

### P1-R4 — Memory/performance evidence

Record asymptotic and representative storage/copy evidence for at least 16x16, 32x32 and 64x64 canvases.

Measure/record:

- authoritative bytes,
- unavoidable output/export copies,
- mutation-path temporary allocation behavior,
- representative replay/export timing as local engineering evidence, not portable correctness truth.

#### P1 acceptance

- Python 3.12/3.13 CI green,
- exact mutation/replay tests,
- invalid bounds/color/batch coverage,
- native + enlarged preview fixture,
- documented memory/copy boundary,
- no LLM/provider/GPU/self-hosted-runner dependency.

**Early measurement:** raster memory/copy microbenchmark.

---

## P2 — Versioned Pixel IR and bounded operation vocabulary

Goal: freeze a compact replayable representation between agent intent and raster mutation.

```text
P2-IR0 schema
 -> P2-IR1 validation
 -> P2-IR2 deterministic executor
 -> P2-IR3 canonical serialization/replay
 -> P2-IR4 operation-vocabulary + compactness budget
```

### P2-IR0 — Schema

Initial authority direction:

```text
ArtIntent
 -> StagePlan
 -> PixelProgram
 -> deterministic executor
 -> Canvas
```

Version all serialized public IR. Do not make Python code itself the canonical program representation.

### P2-IR1 — Validation

Validate structure and finite semantic constraints before raster mutation. Invalid programs fail without partial authoritative mutation.

### P2-IR2 — Executor

Execute only validated operations through the P1 raster authority. Replay requires no LLM/provider.

### P2-IR3 — Canonical serialization and replay

Define deterministic ordering/serialization for the supported IR version and prove round-trip/replay equivalence.

### P2-IR4 — Operation vocabulary and compactness budget

Tool/operation count is a product budget.

- prefer a small orthogonal vocabulary,
- raw pixel patches remain available for precise detail,
- do not add overlapping convenience operations without measured benefit,
- collect representation-size/operation-count evidence against a raw low-level form.

#### P2 acceptance

- versioned IR round-trip,
- invalid IR rejection,
- deterministic executor/replay,
- compact machine-readable replay evidence,
- documented public operation vocabulary and rationale.

**Early measurement:** IR byte/token proxy size, operation count and invalidity microbenchmark.

---

## P3 — Explicit staged authoring pipeline

Goal: make coarse-to-fine pixel construction a first-class executable contract rather than prompt prose.

```text
P3-S0 intent/composition
 -> P3-S1 silhouette
 -> P3-S2 major forms
 -> P3-S3 palette/light ramp
 -> P3-S4 shading
 -> P3-S5 semantic details
 -> P3-S6 outline/cleanup
 -> P3-S7 stage transition + evidence contract
```

### P3-S0 — Intent / composition

Represent bounded art intent such as:

- asset class,
- canvas dimensions,
- intended occupied bounds/margins,
- facing/orientation where relevant,
- symmetry hint/requirement,
- light direction where relevant,
- palette budget.

### P3-S1 — Silhouette

Create/modify the primary occupied shape before detail. Silhouette is a stage, not a claim that recognizability can be deterministically judged.

### P3-S2 — Major forms

Represent a finite set of large regions/forms without introducing an unbounded domain-specific object library.

### P3-S3 — Palette / light ramp

Constrain intentional color growth. Support explicit palette roles/ramp relationships where useful without pretending every style uses one universal shading model.

### P3-S4 — Shading

Apply bounded shading operations consistent with explicit authored light intent where that relationship is objectively defined.

### P3-S5 — Semantic details

Permit small high-information edits after silhouette/forms stabilize. Raw pixel patches remain a bounded escape hatch.

### P3-S6 — Outline / cleanup

Support explicit outline/cleanup operations without making subjective style preferences deterministic truth.

### P3-S7 — Stage transition and evidence contract

Every stage records:

- input stage identity,
- applied Pixel IR operations,
- resulting authoritative pixel digest/metadata,
- optional preview snapshot,
- explicit reason when a stage is skipped.

The agent cannot silently replace the staged pipeline with arbitrary code.

#### P3 acceptance

- one fixture passes the complete staged path,
- stage ordering/skip semantics are deterministic,
- stage snapshots/replay evidence exist,
- stage-local changes can later be localized for P7 repair.

**Preview milestone:** stage-by-stage raster images become inspectable.

---

## P4 — Deterministic pixel QA

Goal: build exact analyzers before any visual critic becomes part of the loop.

```text
P4-Q0 structural invariants
 -> P4-Q1 palette/color QA
 -> P4-Q2 connectivity/isolation QA
 -> P4-Q3 shape/outline QA
 -> P4-Q4 tile-edge QA
 -> P4-Q5 typed findings + policy
```

### P4-Q0 — Structural invariants

- dimensions,
- alpha/background contract,
- occupied bounds/margins,
- visible edge contact,
- empty/non-empty facts.

### P4-Q1 — Palette/color QA

- palette membership,
- exact color count,
- maximum-color policy when explicitly requested,
- transparent-RGB policy where configured.

### P4-Q2 — Connectivity/isolation QA

- deterministic connected components,
- isolated pixels,
- exact topology findings only where objective.

### P4-Q3 — Shape/outline QA

- exact symmetry when the task explicitly requires it,
- finite adjacency/outline diagnostics,
- no universal aesthetic jaggedness claim without an explicit measurable rule.

### P4-Q4 — Tile-edge QA

- left/right equality,
- top/bottom equality,
- explicit corner/edge contracts where requested.

### P4-Q5 — Typed findings and policy

Keep raw facts separate from policy findings. Findings are stable machine-readable records with severity/category/rule identity.

Style, readability, identity and aesthetic quality remain perceptual/human concerns.

#### P4 acceptance

- deterministic QA JSON/equivalent result,
- reproducible findings,
- representative pass/fail fixtures,
- deterministic versus perceptual responsibility documented.

**Early measurement:** QA coverage fixture suite with seeded structural defects.

**Preview milestone:** image evidence can be viewed beside deterministic QA findings.

---

## P5 — Provider-neutral Agent loop and complexity evidence

Goal: introduce the first replaceable model boundary only after raster/IR/stage/QA contracts exist.

```text
P5-A0 provider-neutral interface
 -> P5-A1 compact observation
 -> P5-A2 bounded edit loop
 -> P5-A3 complexity telemetry
 -> P5-A4 recorded/fake-provider CI
 -> P5-A5 first opt-in real-provider smoke
```

### P5-A0 — Provider-neutral interface

Provider/model/SDK/network state does not become canonical pixel/IR state.

### P5-A1 — Compact observation

Expose only the state needed for the next decision, such as:

- intent summary,
- current stage,
- compact structural QA,
- bounded preview/visual observation when needed,
- recent operation/revision context.

Do not repeatedly resend the complete historical transcript/canvas representation by default.

### P5-A2 — Bounded edit loop

```text
request
 -> propose bounded Pixel IR
 -> validate
 -> execute
 -> deterministic QA
 -> compact observation
 -> revise or finish
```

Iteration/tool budgets are explicit.

### P5-A3 — Agent Complexity Budget telemetry

Record when available:

- input/output tokens,
- tool/operation calls,
- exposed concept count,
- visual observation calls,
- iterations/revisions,
- changed pixels,
- wall time,
- API cost,
- human interventions,
- failure category.

### P5-A4 — Recorded/fake-provider CI

Portable CI proves deterministic orchestration with fake or recorded model outputs. Live paid/network providers do not gate repository correctness.

### P5-A5 — First opt-in real-provider smoke

Run one explicitly owner-triggered real-provider smoke only after A0-A4 are green.

**Owner gate:** choose/pin the first provider/model before A5.

#### P5 acceptance

- deterministic CI without secrets/network,
- provider-neutral boundary proven,
- bounded loop and failure states covered,
- complexity evidence captured,
- at least one optional real-provider smoke documented when the owner approves.

**Early measurement:** Agent token/tool/iteration pilot before gallery work.

**Preview milestone:** first actual AI-authored TracePixel raster result.

---

## P6 — Preview evidence and mobile gallery

Goal: make outputs easy to judge from mobile without a desktop editor.

```text
P6-V0 preview bundle
 -> P6-V1 stage contact sheet
 -> P6-V2 QA/metrics composition
 -> P6-V3 static HTML gallery
 -> P6-V4 GitHub artifact publishing
 -> P6-V5 mobile review flow
 -> P6-V6 optional home-PC runner
```

### P6-V0 — Preview bundle

Bundle native PNG, enlarged nearest preview, stage images, deterministic QA, intent summary and complexity evidence.

### P6-V1 — Stage contact sheet

Produce a deterministic review sheet across authored stages without altering source pixels.

### P6-V2 — QA/metrics composition

Present structural QA and Agent complexity evidence beside the image while keeping deterministic/perceptual authority separate.

### P6-V3 — Static HTML gallery

Generate a static review view suitable for phone browsers.

### P6-V4 — GitHub artifact publishing

Publish deterministic preview bundles through explicit workflows/artifacts.

### P6-V5 — Mobile review flow

Prove the owner can identify the task, final output, stage progression, QA status and key complexity evidence from mobile.

### P6-V6 — Optional home-PC runner

A Windows self-hosted runner may be added only as an **owner-triggered preview execution target**. It must never automatically execute untrusted public pull-request code.

**Owner gate:** connecting/enabling the home runner requires explicit owner approval.

#### P6 acceptance

- deterministic preview bundle,
- stage contact sheet,
- static HTML view,
- artifact workflow,
- documented mobile review path,
- public-PR safety preserved.

---

## B0 — Matched development-visible architecture benchmark

Goal: determine whether the architecture improves constrained asset authoring before expanding scope.

```text
B0-F0 preregistration freeze
 -> B0-H0 matched harness
 -> B0-B0 baseline adapters
 -> B0-S0 scored visible cohort
 -> B0-P0 immutable postmortem
```

### B0-F0 — Freeze

Freeze in a commit before scoring:

- visible task set and hidden structural constraints,
- baseline versions/adapters,
- provider/model identities/settings,
- token/tool/time/cost/retry budgets,
- deterministic and perceptual scoring rules,
- exclusion/failure policy,
- trial count.

### B0-H0 — Harness

Use one result schema and preserve every attempt, including unsuccessful runs.

### B0-B0 — Baselines

Run only baselines that can be matched honestly. Candidate families remain defined in `BENCHMARK.md`.

### B0-S0 — Scored cohort

Concentrate on T1-T3 with T0 sanity tasks. T4 enters only with explicit tiling metrics. T5+ is not required for the initial claim.

### B0-P0 — Immutable postmortem

Preserve the scored cohort and classify failures. Improvements happen after the frozen cohort, not by rerunning B0 until TracePixel wins.

#### B0 acceptance

- frozen preregistration commit,
- complete scored evidence,
- all unsuccessful attempts preserved,
- complexity + structural + perceptual summaries,
- postmortem with concrete architecture follow-ups.

---

## P7 — Targeted repair and human feedback loop

Goal: replace full regeneration with bounded, reviewable correction where possible.

```text
P7-F0 feedback/finding intake
 -> P7-F1 affected stage/region localization
 -> P7-F2 minimal repair plan
 -> P7-F3 re-execute + re-QA
 -> P7-F4 before/after evidence
 -> P7-F5 human-feedback contract
```

Required direction:

```text
finding / human feedback
 -> affected region/stage
 -> minimal repair plan
 -> deterministic mutation
 -> re-QA
 -> comparison evidence
```

Measure changed pixels, changed operations, revision cost and whether unaffected regions remained stable where required.

#### P7 acceptance

- deterministic local repair path,
- changed-pixel accounting,
- before/after preview + QA evidence,
- bounded human feedback representation,
- complexity telemetry distinguishes repair from regeneration.

---

## B1 — Held-out generalization benchmark

```text
B1-F0 held-out freeze
 -> B1-S0 multiple-trial scored cohort
 -> B1-P0 generalization postmortem
```

B1 starts only after B0 postmortem-driven architecture changes are implemented.

### B1-F0 — Freeze

Freeze unseen variants and all budgets/scoring before runs.

### B1-S0 — Scoring

Use multiple trials for nondeterministic methods and preserve failures. Keep deterministic structural score, perceptual evaluation and complexity evidence separate.

### B1-P0 — Postmortem

Document generalization boundaries rather than turning one benchmark into a universal art-quality claim.

#### B1 acceptance

- held-out frozen cohort,
- preserved unsuccessful runs,
- generalization results across matched baselines,
- explicit scope/promotions for P8.

---

## P8 — Production breadth

Only after B1 justifies the architecture, widen asset classes in bounded promotions.

```text
P8-B0 richer item icons
 -> P8-B1 props/furniture
 -> P8-B2 tileable blocks/terrain decoration
 -> P8-B3 autotile/variant consistency
 -> P8-B4 simple creatures
 -> OWNER PROMOTION GATE
 -> P8-B5 humanoids
 -> OWNER PROMOTION GATE
 -> P8-B6 animation/multi-frame consistency
```

Each breadth child requires representative fixtures, deterministic contracts where applicable, preview evidence and complexity measurements.

Humanoids and animation are not automatic roadmap creep: they change identity/pose/temporal consistency requirements and require explicit promotion decisions.

---

## P9 — Trace2D adapter experiment

Begin only if independent TracePixel evidence is positive and the owner explicitly approves integration work.

```text
P9-T0 adapter contract
 -> P9-T1 Trace2D-consumable handoff evidence
 -> P9-T2 matched integration trial
 -> P9-T3 go/no-go decision
```

### P9-T0 — Adapter contract

Emit provider-neutral RGBA/metadata/manifest evidence rather than embedding Python/LLM/provider types in Trace2D runtime state.

### P9-T1 — Handoff

Feed outputs through the existing Trace2D deterministic Sprite/Asset preparation/import authority.

### P9-T2 — Integration trial

Compare the adapter workflow against the existing Trace2D Sprite-generation/import workflow under a frozen task/budget contract.

### P9-T3 — Go / no-go

Adopt only demonstrated useful seams. A successful TracePixel project does not automatically imply its implementation belongs inside the Trace2D runtime.

#### P9 acceptance

- no Python/LLM dependency in Trace2D runtime,
- no provider state in canonical Trace2D assets,
- deterministic Trace2D import/QA remains authoritative,
- integration benchmark complete,
- explicit go/no-go record.
