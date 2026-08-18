# TracePixel

Generator-neutral deterministic pixel-asset quality, repair and benchmarking toolkit.

TracePixel explores a production question:

> **Can heterogeneous AI/RAW/external raster generators be turned into game-ready pixel assets through deterministic inspection, normalization, bounded repair, exact replay/evidence and explicit human review?**

The project originally centered staged/direct PixelProgram generation. B0/B1/G8 evidence did not prove that complex direct authoring was perceptually superior to simpler RAW generation, and G8 humanoid evidence selected an owner-confirmed **PIVOT** on 2026-08-18. The direct generator is retained as an optional backend/control and precision-repair path, not the privileged production path.

See [`docs/G8_DIRECT_AUTHORING_POSTMORTEM.md`](docs/G8_DIRECT_AUTHORING_POSTMORTEM.md) and [`docs/P11_GENERATOR_NEUTRAL_PIVOT.md`](docs/P11_GENERATOR_NEUTRAL_PIVOT.md).

## Product contract

> Humans define intent and judge the result. AI owns bounded iteration in between.

> Deterministic where possible. Multimodal where necessary. Human judgment at the end.

TracePixel is not trying to beat every image generator at raw illustration quality. It targets the parts that remain valuable regardless of which generator is best today:

- exact RGBA8 raster authority,
- deterministic QA for objective constraints,
- generator-neutral candidate intake,
- palette/alpha/grid/bounds and other exact normalization where justified,
- bounded local pixel repair,
- exact before/after replay and changed-pixel evidence,
- provider/token/iteration/wall-time telemetry,
- retained negative evidence rather than retry-until-pretty behavior,
- explicit owner perceptual review.

## Intended post-pivot pipeline

```text
intent / frozen experiment
 -> replaceable generator, RAW path, or retained external candidate
 -> TracePixel candidate import / Canvas
 -> deterministic QA + normalization
 -> bounded local repair when useful
 -> owner perceptual review
 -> exact replay / evidence / telemetry
 -> game-ready output or explicit retained rejection
```

A generator may be nondeterministic. Once one concrete candidate enters TracePixel, deterministic code owns exact facts and any exact repair mutations.

The following must not be collapsed into one score:

```text
objective structural correctness -> deterministic code
ambiguous perceptual quality      -> optional bounded multimodal evidence
final aesthetic/product approval  -> human owner
```

## Direct authoring remains, but changes role

The existing staged/PixelProgram direct path is not deleted. It may still be useful for:

- small/simple assets where benchmark evidence supports it,
- a matched control against RAW/external generators,
- precision local repair where preserving unaffected pixels matters.

It must not gain new humanoid schemas, solvers or operations merely to force a benchmark win. New direct-generation breadth requires evidence that it beats or complements simpler alternatives on quality, cost, repairability, reproducibility or another explicit production dimension.

## Owner-operated loop

Repository state is designed so a fresh agent can continue without hidden chat history.

Normal owner command:

```text
@GitHub TracePixel 다음 작업 진행해줘
```

The agent resolves live issue/PR state and `config/tracepixel.core-lane.json`.

For provider-backed experiments the required loop is:

```text
freeze task/backends/budgets/review criteria
 -> owner-triggered bounded run
 -> native PNG + enlarged preview + deterministic QA + cost evidence
 -> awaiting-owner-review
 -> explicit owner ACCEPT / REJECT + natural-language feedback
 -> freeze result OR bind feedback to the exact artifact
 -> only preregistered bounded repair/regeneration
 -> review again or stop
```

When a result is awaiting owner review, automation stops before another provider call. The owner can reply naturally; the agent conservatively converts that feedback into the existing bounded human-feedback/repair contracts.

TracePixel does **not** use an autonomous `aesthetic_score >= threshold` regeneration loop. Cheap deterministic QA/normalization may repeat without provider calls; subjective acceptance remains human.

## Current lane

The active post-G8 lane is **P11 — generator-neutral quality-controller pivot and owner review loop**, tracked by issue #151.

Its first production-facing north-star benchmark is planned around **128x128 static game art**. A later 32x32 animation/sprite-sheet benchmark is an owner decision after P11 evidence; G9 direct animation remains blocked meanwhile.

## Evidence-first output

A production/promotion experiment should retain, as applicable:

- native-size PNG,
- nearest-neighbor enlarged preview,
- exact candidate/backend provenance,
- deterministic QA JSON,
- normalization/repair before-and-after evidence,
- changed-pixel/operation evidence,
- provider and Agent complexity/cost evidence,
- explicit owner review state and feedback binding,
- retained unsuccessful/negative attempts.

Normal portable CI remains provider-free. Paid/model execution is owner-triggered and bounded by a frozen experiment contract.

## Relationship to external generators and Trace2D

Public generators such as PerfectPixel and sprite-gen are comparison/interop precedents, not stacks TracePixel automatically clones. The preferred boundary is generator-neutral: external/generated RGBA and metadata enter TracePixel's deterministic quality/review path.

TracePixel remains independent from Trace2D until G10 is explicitly approved. A future adapter should feed provider-neutral RGBA/metadata/manifests into Trace2D's existing Sprite/Asset preparation boundaries without putting Python, an LLM or a provider into engine runtime authority.

## Repository operation

- live GitHub issue/PR/check state is highest authority,
- `config/tracepixel.core-lane.json` is the machine-readable continuation lane,
- `PROJECT_STATUS.md` is the current explanatory handoff,
- `AGENTS.md` defines non-negotiable Agent rules,
- `docs/DECISION_GATES.md` defines owner decisions automation may not silently cross.

## License

MIT. Reference projects are studied for architecture and benchmark design; their code and licenses remain independent.
