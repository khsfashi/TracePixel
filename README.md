# TracePixel

Agent-first deterministic pixel asset authoring and benchmarking toolkit.

TracePixel explores a narrow question: **how far can an AI agent author small, game-ready raster assets when the pixels are produced by deterministic tools instead of opaque image generation?**

## Product contract

> Humans define intent and judge the result. AI owns the iteration in between.

> Deterministic where possible. Multimodal where necessary. Human judgment at the end.

The project is not trying to beat general image generators at arbitrary illustration. It targets small, constrained assets where exact pixels, palettes, reproducibility, editability and machine-verifiable rules matter.

Initial target classes include icons, props, tiles and other compact non-humanoid assets. Characters and animation are later difficulty tiers, not the starting benchmark.

## Intended pipeline

```text
intent
 -> constrained art plan
 -> silhouette
 -> major forms
 -> shading
 -> semantic details
 -> outline / pixel cleanup
 -> deterministic QA
 -> perceptual review
 -> targeted repair
 -> game-ready PNG + evidence
```

The LLM chooses *what* to do. A validated Pixel IR and deterministic raster operations own *how pixels change*. Arbitrary model-generated Python is a benchmark baseline, not the production authority.

## Evidence-first output

A generation run should eventually produce:

- native-size PNG,
- nearest-neighbor enlarged preview,
- stage-by-stage preview sheet,
- deterministic QA JSON,
- agent complexity/cost evidence,
- optional perceptual-review evidence,
- a mobile-friendly static preview page.

Normal CI stays on GitHub-hosted runners. A future Windows self-hosted runner is preview-only and must never execute untrusted public pull-request code automatically.

## Repository operation

`PROJECT_STATUS.md` and `config/tracepixel.core-lane.json` define the continuation lane. `AGENTS.md` defines the non-negotiable agent rules.

The intended owner workflow is:

```text
@GitHub TracePixel 다음 작업 진행해줘
```

A fresh agent should recover the exact next task from repository state without relying on previous chat history.

## Relationship to Trace2D

TracePixel remains an independent experiment until benchmarks justify integration. If successful, its provider-neutral generation/evidence surfaces can later feed Trace2D's existing Sprite generation and Asset Intelligence boundaries instead of coupling Python or a specific model into the engine runtime.

## License

MIT. Reference projects are studied for architecture and benchmark design; their code and licenses remain independent.
