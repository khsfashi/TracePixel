# Architecture

## 1. Authority model

TracePixel separates five concerns:

```text
User Intent
  -> Agent Planning
  -> Versioned Pixel IR
  -> Deterministic Raster/QA
  -> Evidence Bundle
  -> Perceptual/Human Review
```

Canonical pixel truth begins at validated Pixel IR plus deterministic execution. A model response, screenshot, VLM opinion or provider transcript is evidence/input, never canonical pixel state by itself.

## 2. Planned package boundaries

```text
tracepixel/
  model/       # versioned intent/IR data, no provider SDK types
  raster/      # deterministic canvas + primitive execution
  qa/          # exact structural analyzers
  pipeline/    # explicit stage orchestration
  agent/       # provider-neutral decision loop
  providers/   # optional external adapters
  preview/     # PNG/contact-sheet/gallery evidence
  benchmark/   # harness and metrics
```

The CLI is an adapter over library APIs. It must not own hidden state unavailable to tests or future MCP/automation surfaces.

## 3. Data direction

```text
prompt / explicit constraints
 -> ArtIntent
 -> StagePlan
 -> PixelProgram(vN)
 -> ValidateProgram
 -> ExecuteProgram
 -> Canvas/RGBA8
 -> AnalyzeDeterministicQA
 -> PreviewBundle
 -> optional PerceptualReview
 -> optional RepairPlan
```

A concrete PixelProgram must replay without a provider call.

## 4. Pixel storage

P1 should benchmark and choose a compact contiguous authority, initially favoring one of:

- packed RGBA8 byte storage, or
- palette-index buffer + explicit palette when the operation requires indexed semantics.

Do not use one heap object per pixel. Views should avoid copying decoded buffers merely for inspection. Derived enlarged previews are separate outputs, never authoritative source pixels.

## 5. Operation design

Operations exist at three potential levels:

- low-level exact mutation: pixel/batch pixel,
- geometric primitive: line/rect/fill/polygon where deterministic semantics are useful,
- art-aware operation: outline/shade/cleanup only after benchmark evidence shows a stable semantic contract.

The public Agent surface should be the smallest vocabulary that expresses representative work efficiently. A large tool catalogue is considered an Agent-complexity cost, not automatically a feature.

Every operation requires:

- explicit bounds behavior,
- explicit palette/color behavior,
- deterministic validation before mutation,
- deterministic ordering,
- transactional failure where partial mutation would be ambiguous.

## 6. Stage architecture

The staged pipeline is evidence-oriented, not a hidden prompt trick.

```text
composition
silhouette
forms
palette/light
shading
detail
outline/cleanup
```

Each stage may emit a snapshot descriptor and optional image artifact. The authoritative state is still the current canonical canvas/IR; snapshots are review evidence. Snapshot retention must be bounded so large benchmark batches do not accidentally retain every full buffer forever.

## 7. QA authority

Deterministic QA owns only objectively derivable facts. It should expose raw measurements separately from policy findings.

Example:

```text
raw: palette_color_count = 7
policy: max_palette_colors = 6
finding: palette_limit_exceeded
```

A VLM cannot override a deterministic failure. A deterministic pass cannot claim the art is attractive or recognizable.

## 8. Provider boundary

Providers receive provider-neutral context and return bounded decisions/operations. Provider SDK objects, model-specific message types, API keys and retry state stay outside core model/raster/QA packages.

Portable CI never requires live providers. Recorded responses or deterministic fake agents validate orchestration.

## 9. Preview and remote execution

Preview output is an offline evidence product.

```text
run-id/
  request.json
  program.json
  final.png
  final@8x.png
  stages/*.png
  qa.json
  metrics.json
  index.html
```

Initial CI generates deterministic fixture previews on GitHub-hosted runners. Later, an owner-triggered Windows self-hosted runner may execute expensive/local-model previews and upload the same bundle as an Actions artifact or static Pages input.

Security invariant for the public repository: no automatic untrusted `pull_request` event may execute arbitrary repository code on the home runner.

## 10. Trace2D integration boundary

TracePixel remains an external producer. A future Trace2D adapter should terminate at a simple owned image/metadata/manifest boundary. Trace2D then revalidates through its own Sprite/Asset preparation contracts. No TracePixel Python object, provider object or Agent state becomes Trace2D runtime truth.
