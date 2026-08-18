# TracePixel

> **Status: ARCHIVED / research complete (2026-08-18).**
>
> TracePixel is no longer an active product or R&D roadmap. Historical code, benchmarks, retained failures and deterministic raster experiments remain available as research evidence.

TracePixel explored whether an AI Agent could author game-ready pixel art through deterministic raster operations, staged contracts, exact replay, deterministic QA and bounded repair.

The central production thesis did **not** earn continued standalone development:

- B0 showed that deterministic staged authoring could satisfy structural rules while producing substantially weaker human-visible results than a simpler RAW baseline.
- B1 corrected the premature deterministic stop condition and recovered human acceptance on the small benchmark, but did not demonstrate perceptual superiority and required materially more orchestration/provider work.
- simple-creature authoring proved feasibility, not a matched advantage over RAW or external generation.
- G8 static humanoid authoring produced retained technically valid candidates that were owner-rejected on product quality.
- the matched RAW humanoid remained below production quality but was clearer on important human-visible dimensions without establishing a compensating cost advantage for the staged TracePixel path.
- the later generator-neutral quality-controller direction overlapped substantially with Trace2D's existing Sprite processing/orchestration stack and mature external pixel/sprite tooling.

The owner therefore chose to stop expanding TracePixel rather than invent another standalone product reason.

## Final disposition

TracePixel is preserved as a completed research repository.

Retained useful work includes:

- exact RGBA8 Canvas authority,
- PixelProgram validation/execution and canonical replay,
- transactional raster mutation,
- deterministic QA primitives,
- bounded/local repair experiments,
- exact PNG/digest/diff evidence,
- owner feedback bound to exact artifacts,
- provider/token/iteration/wall-time telemetry,
- B0/B1 matched benchmark evidence,
- simple-creature evidence,
- immutable G8 humanoid negative evidence,
- P11-X0/X1 generator-neutral candidate identity and owner-review protocol.

These capabilities remain historical/reference material. Their existence is not authorization to resume the old roadmap.

## Product successor

The human-facing AI asset production product now belongs to **Trace2D Asset Studio** (`khsfashi/Trace2D#318`).

That product owns the intended experience:

```text
project asset-production request
 -> replaceable generation backend(s)
 -> bounded candidate set
 -> deterministic Sprite processing/import
 -> Workspace showroom / owner review
 -> feedback / alternatives / approval
 -> project asset library
 -> canonical SpriteAsset / animation
 -> immediate game use
```

Trace2D should reuse its existing SPP0-SPP5, Sprite/animation/runtime, WorkResult, Workspace and transactional authoring authority instead of rebuilding them here.

If a historical TracePixel technique later proves useful to a concrete Trace2D workload, the smallest relevant idea/code may be selectively upstreamed after an explicit matched proof. TracePixel itself does not resume development by default.

## Archived owner workflow

`@GitHub TracePixel 다음 작업 진행해줘` must **not** open a new implementation lane.

A fresh Agent should report that the repository is archived/research-complete and direct product work to Trace2D Asset Studio. Only an explicit owner decision to unarchive/reopen TracePixel may create new roadmap authority.

Maintenance needed solely to preserve repository accessibility, security, reproducibility or historical evidence may be handled only when explicitly requested; it must not silently become feature development.

## Evidence integrity

Historical scored and negative evidence is immutable. Do not rerun, overwrite, relabel or cherry-pick old attempts to improve the recorded conclusion.

The project result is intentionally preserved even though the original product thesis was not promoted.

See `docs/ARCHIVE.md` for the final research conclusion and handoff.

## License

MIT. External projects remain independent references unless separately adopted by Trace2D under a current license/version review.
