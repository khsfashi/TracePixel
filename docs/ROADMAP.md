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

Benchmarks are deliberately interleaved. TracePixel must not wait until it is feature-complete before testing whether its agent-facing architecture is actually efficient.

---

## P0 — Repository and benchmark foundation

Deliver:

- repository/agent authority rules,
- machine-readable continuation lane,
- minimal Python package and doctor command,
- GitHub-hosted portable CI,
- architecture contract,
- benchmark preregistration,
- reference-project register.

No LLM provider dependency yet.

## P1 — Deterministic raster core

Build the smallest authoritative pixel engine.

Required concepts:

- exact integer canvas dimensions,
- transparent/opaque RGBA8 truth,
- finite palette and indexed-color-friendly representation,
- deterministic pixel set/batch set,
- line/rect/fill primitives only as justified by tests,
- exact native PNG export,
- nearest-neighbor enlarged preview export,
- byte/replay evidence for the same canonical input.

Avoid Python object-per-pixel storage in authoritative steady operations.

## P2 — Pixel IR and bounded operation vocabulary

Freeze a compact, versioned, serializable program between Agent intent and raster mutation.

Initial direction:

```text
ArtIntent
 -> StagePlan
 -> PixelProgram
 -> deterministic executor
 -> Canvas
```

Operations must be validated before mutation and replayable without an LLM. Tool count is a budget: do not expose dozens of overlapping operations without benchmark evidence.

## P3 — Staged authoring pipeline

Implement an explicit coarse-to-fine contract:

1. composition / bounds,
2. silhouette,
3. major forms,
4. palette/light ramp,
5. shading,
6. semantic detail,
7. outline/cleanup.

Stage snapshots are explicit evidence. Stages may be skipped only when the authored plan says why; the Agent cannot silently replace the pipeline with arbitrary code.

## P4 — Deterministic pixel QA

Add exact analyzers before adding a visual critic.

Candidate evidence:

- dimensions and alpha invariants,
- palette membership/count,
- occupied bounds and edge contact,
- connected components,
- isolated pixels,
- exact or contract-defined symmetry,
- outline/adjacency diagnostics,
- requested tiling-edge equality,
- light-direction checks only where the authored contract makes them objective.

Style/readability/identity are not deterministic findings.

## P5 — Provider-neutral Agent loop

Introduce the first replaceable model boundary.

```text
request
 -> provider-neutral Agent
 -> compact state/preview observation
 -> bounded Pixel IR operations
 -> deterministic execution/QA
 -> revision or finish
```

Record Agent Complexity Budget data. Paid/network calls remain opt-in; CI uses recorded/fake agent responses.

## P6 — Preview evidence and mobile gallery

Make outputs human-reviewable without a desktop editor.

Each preview bundle should support:

- native image,
- nearest-neighbor enlarged image,
- stage contact sheet,
- QA summary,
- prompt/intent summary,
- complexity metrics,
- static HTML view.

GitHub-hosted CI can build deterministic fixtures. A home Windows self-hosted preview runner is a later owner-triggered execution target only.

## B0 — Matched architecture benchmark

Run frozen development-visible tasks across matched baselines. Establish whether TracePixel improves success, iteration cost and deterministic compliance on easy-to-moderate icons/props before expanding scope.

Do not use B0 as the final generalization claim.

## P7 — Targeted repair and feedback loop

Support bounded edits rather than full regeneration.

Required direction:

```text
finding / human feedback
 -> affected region/stage
 -> minimal repair plan
 -> deterministic mutation
 -> re-QA
 -> comparison evidence
```

Measure changed pixels and revision cost.

## B1 — Held-out benchmark

Freeze unseen task variants before scoring. Compare against the same pinned baselines, include multiple trials where nondeterministic providers are used, and preserve all unsuccessful runs.

## P8 — Production breadth

Only after B1 justifies the architecture, widen asset classes:

- richer item icons,
- props/furniture,
- tileable blocks,
- autotile variants,
- terrain decorations,
- simple creatures.

Humanoids and multi-frame animation require an explicit promotion gate because identity/pose consistency changes the problem substantially.

## P9 — Trace2D adapter experiment

If independent evidence is positive, build a thin provider-neutral adapter that emits Trace2D-consumable RGBA/metadata/manifest evidence.

Hard constraints:

- no Python/LLM dependency in Trace2D runtime,
- no model/provider type in canonical Trace2D asset state,
- Trace2D deterministic import/QA remains authoritative after handoff,
- integration gets its own benchmark against the existing Trace2D Sprite workflow.
