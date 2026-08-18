# TracePixel

Deterministic raster R&D for AI-operated game-asset workflows.

TracePixel started by asking whether staged/direct LLM pixel authoring could beat simpler RAW approaches. B0/B1/G8 evidence did not support that as a production product thesis. A later generator-neutral quality-controller pivot produced useful owner-review machinery, but broad QA/normalization also overlaps heavily with Trace2D's completed Sprite processing stack and existing public tools.

The current question is narrower:

> **Can deterministic raster operations give an Agent a measurable advantage on precision editing, protected-region preservation, collateral-damage control, exact replay or similarly specific problems that are not already solved well enough elsewhere?**

TracePixel is therefore a **research lab**, not the product owner for an Asset Studio, sprite showroom or general game-asset manager.

The human-facing production product belongs to **Trace2D Asset Studio** (`khsfashi/Trace2D#318`).

## Current role

TracePixel preserves and experiments with:

- exact RGBA8 Canvas authority,
- PixelProgram validation/execution and canonical replay,
- transactional raster mutation,
- exact PNG/digest/diff evidence,
- deterministic QA primitives,
- bounded local repair,
- owner feedback bound to exact artifacts,
- provider/token/iteration/wall-time evidence,
- matched benchmark harnesses and immutable failures.

These are research capabilities, not a claim that TracePixel should own the full production pipeline.

## Explicitly not owned here

TracePixel does **not** own:

- an end-user Asset Studio/showroom,
- the project asset library,
- broad sprite generation orchestration,
- the best image/sprite generator,
- generic alpha/palette/grid/frame processing already owned by Trace2D SPP0-SPP5,
- animation/runtime Sprite authority,
- autonomous aesthetic approval.

Trace2D already owns canonical SpriteAsset/animation/runtime state, deterministic Sprite processing/import/generation orchestration, WorkResult and Workspace review. TracePixel should not duplicate that architecture.

## Active P12 research lane

Issue #155 owns the current lane:

```text
P12-R0 responsibility diff + unique-hypothesis freeze
 -> P12-R1 precision-edit matched benchmark freeze
 -> P12-R2 owner-triggered matched run
 -> P12-P0 KEEP-AS-LAB / UPSTREAM / ARCHIVE decision
```

The default candidate hypothesis is **precision raster editing with protected-region preservation**.

Example:

```text
Shorten only the sword hilt.
Everything outside the allowed region must remain byte-identical.
```

A matched experiment should compare RAW/image-edit/TracePixel where honest and report separately:

- human-visible requested-change quality,
- exact protected-pixel violations,
- total/collateral changed pixels,
- provider calls/tokens/time,
- revisions,
- exact replay/evidence.

TracePixel only earns further implementation when such evidence shows a practical advantage.

## Historical results kept intact

The repository preserves B0/B1/G8 evidence, including owner-rejected humanoid results. Do not rerun or rewrite historical evidence merely to improve the narrative.

P11-X0/X1 are also retained as useful research: generator-neutral candidate identity plus the owner-run / `awaiting-owner-review` protocol. P11-X2 and later broad quality-controller work are superseded by P12.

## Owner workflow

Normal continuation remains:

```text
@GitHub TracePixel 다음 작업 진행해줘
```

A fresh Agent resolves live GitHub state and `config/tracepixel.core-lane.json`.

P12-R0 is provider-free and feature-free. Before any new implementation, it must establish that the proposed problem is not already adequately owned by Trace2D or existing tools.

Later provider-backed experiments reuse the retained owner protocol:

```text
freeze experiment
 -> owner-triggered bounded run
 -> retain exact artifacts/evidence
 -> awaiting-owner-review
 -> owner natural-language feedback
 -> exact feedback binding
 -> bounded continuation or stop
```

No `while aesthetic_score < threshold: regenerate()` loop is allowed.

## Promotion to Trace2D

TracePixel does not automatically integrate with Trace2D because code exists. A technique is upstreamed only after matched evidence shows a product advantage for Trace2D Asset Studio or another explicit Trace2D workflow.

If P12 finds no unique advantage, preserving this repository as a documented research result and stopping expansion is an acceptable outcome.

## Repository operation

- live GitHub issue/PR/check state is highest authority,
- `config/tracepixel.core-lane.json` is the machine-readable continuation lane,
- `PROJECT_STATUS.md` is the explanatory handoff,
- `AGENTS.md` defines Agent rules,
- issue #155 owns the active research hypothesis.

## License

MIT. External projects remain independent references unless a current license/version review explicitly promotes an integration.
