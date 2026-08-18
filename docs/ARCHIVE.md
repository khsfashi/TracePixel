# TracePixel Archive Disposition

**Status: ARCHIVED / RESEARCH COMPLETE**  
**Owner decision date: 2026-08-18**

## Decision

TracePixel is complete as a research project and stops standalone development.

The repository is preserved because its implementation, matched benchmarks, exact evidence and retained failures answer useful engineering questions. It is not preserved as an active product roadmap.

A generic continuation request such as `@GitHub TracePixel 다음 작업 진행해줘` must not reopen the project. Only an explicit owner decision to unarchive/reopen TracePixel can establish new active scope.

## Original question

TracePixel began from the hypothesis that an LLM/Agent might produce stronger game-ready pixel assets when raster creation was constrained through deterministic tools, explicit stages, exact replay, deterministic QA and targeted repair rather than opaque image generation or simpler RAW authoring.

The research separated:

- structural correctness,
- perceptual/human-visible quality,
- iteration/provider cost,
- repairability/replayability,
- failure evidence.

That separation is retained as a useful lesson even though the standalone product thesis was not promoted.

## Evidence-based conclusion

### B0

RAW and staged methods both completed structurally, but the staged path could stop once deterministic QA became green before completing the intended artistic work. Human review strongly preferred RAW.

This proved that deterministic structural success is not equivalent to perceptual completion.

### B1

After fixing the stop condition, the staged path completed all artistic stages and recovered human acceptance on the small held-out benchmark.

However, it did not establish perceptual superiority over RAW and required materially more orchestration/provider work. The fix showed that the staged architecture could be made semantically correct, not that it was a better production generator.

### Simple creature

TracePixel successfully authored a static simple quadruped through the existing deterministic path.

That established feasibility only. Without a matched RAW/external baseline, it did not establish an incremental product advantage.

### G8 humanoid

Two technically valid TracePixel humanoid candidates were retained and owner-rejected on product quality. The second candidate improved silhouette/dynamic pose/identity cues but remained below the owner's standard on anatomy, equipment attachment, material readability and pixel-cluster craft.

A matched one-call RAW humanoid remained below production quality too, but was clearer on several important human-visible criteria while runtime cost was broadly similar enough that the more complex TracePixel staged architecture did not earn a compensating advantage.

This was the decisive evidence against further humanoid-specific schema/controller expansion.

### Generator-neutral quality-controller pivot

P11-X0/X1 produced useful research infrastructure:

- generator-neutral candidate identity,
- exact run/candidate/native-artifact binding,
- owner-run budget freezing,
- `awaiting-owner-review` stop semantics,
- natural-language owner feedback without promoting aesthetics into deterministic truth.

But broad P11-X2+ QA/normalization/production expansion overlapped substantially with Trace2D's completed Sprite processing/orchestration stack and existing public pixel/sprite tooling.

Continuing it as another standalone product would repeat the same architecture-before-value mistake.

## Why P12 was not continued

P12 proposed one final narrow R&D hypothesis around protected-region precision editing and collateral-damage measurement.

The owner has decided that continuing to search for a new independent TracePixel purpose is no longer worthwhile. Therefore:

- P12-R0/R1/R2/P0 do not need to execute,
- **No P12-R1/R2 provider run is authorized**, 
- no new precision-edit feature is required merely to justify retaining the repository,
- no new PixelProgram vocabulary, QA family, provider integration or product surface should be added by default.

If Trace2D later encounters a concrete production problem where a historical TracePixel technique appears useful, that need should be proven from the Trace2D workload first. The smallest useful idea/code can then be upstreamed without reopening this repository as a product.

## Product handoff

The original end-user ambition survives in **Trace2D Asset Studio** (`khsfashi/Trace2D#318`), not in TracePixel.

The product target is:

```text
human project intent
 -> set-level asset production request
 -> replaceable image/sprite generation backend(s)
 -> bounded candidate set
 -> deterministic Trace2D Sprite processing/import
 -> Workspace showroom/review queue
 -> owner choose/reject/feedback/alternatives
 -> approved project asset library
 -> canonical SpriteAsset / animation
 -> game use
```

Trace2D already owns the relevant canonical Sprite/animation/runtime, SPP0-SPP5 processing and provider-neutral generation orchestration, WorkResult, Workspace review and transactional Sprite-authoring seams.

TracePixel must not reopen a competing Asset Studio, showroom, asset library, provider marketplace or broad sprite-production stack.

## Preserved research assets

Keep intact:

- Canvas/RGBA8 authority,
- PixelProgram and canonical replay,
- deterministic QA primitives,
- transactional raster mutation,
- P7 feedback/local repair contracts,
- P11-X0/X1 owner-review machinery,
- B0/B1 benchmark fixtures/results/postmortems,
- simple-creature evidence,
- G8 native PNGs/previews/telemetry/complexity/QA evidence,
- matched RAW evidence,
- all negative/scored result digests and regression checks.

Do not regenerate, overwrite, relabel or cherry-pick frozen evidence to improve the historical outcome.

## Agent rule after archive

A fresh Agent must not reopen work simply because an old issue, roadmap stage, TODO or historical test mentions future work.

When the repository remains archived:

1. report the archived/research-complete disposition,
2. do not create a feature/research PR,
3. point product asset work to Trace2D Asset Studio #318,
4. only perform explicitly requested archival maintenance.

An explicit owner decision to unarchive is required before any new TracePixel research or feature roadmap exists.

## Final interpretation

TracePixel is not being hidden or deleted because the thesis changed.

Its final value is the evidence that:

> deterministic structure and replayability can improve control and verification, but they do not automatically improve visual quality; complex direct LLM raster authoring did not demonstrate enough quality-per-complexity advantage to justify a standalone production generator, and overlapping product responsibilities are better consolidated into Trace2D Asset Studio.

That is the completed research result.
