# Owner Decision Gates

TracePixel is designed for autonomous continuation between explicit human decisions. This file defines decisions that an Agent must **not** silently make merely because implementation can continue.

When a gate is reached, stop the affected lane, summarize the evidence/trade-offs and ask the repository owner. Unrelated already-authorized work may continue only if it does not prejudge the decision.

## Decision principles

- Prefer evidence from committed fixtures/benchmarks over preference guesses.
- Separate reversible implementation detail from product-scope decisions.
- Do not use a benchmark result to silently broaden project scope.
- A recorded long-term product-scope approval does not override upstream engineering checkpoints or authorize pulling later implementation into an earlier lane.
- Record resolved owner decisions in the relevant issue/contract/status document.
- If an existing owner decision already resolves the exact question, do not ask again.
- Deterministic QA may reject objective defects, but it may never auto-approve subjective aesthetics.
- A rejected visual result remains retained evidence; do not retry until it disappears from the narrative.

## G1 — Authoritative pixel representation

**Earliest lane:** P1-R0.

Default direction is a compact contiguous RGBA8 authority with palette/indexed workflows layered explicitly where useful.

Stop for owner review if a proposal would instead make palette indices the primary canonical pixel authority, introduce multiple competing canonical pixel stores, or materially complicate the simple RGBA8 baseline.

Decision evidence should include storage/memory, deterministic replay, palette-edit/Agent compactness, conversion/copy cost and export/consumer compatibility.

## G2 — Image/PNG dependency

**Earliest lane:** P1-R2.

A tiny well-understood dependency may be justified, but do not add a large image stack merely for PNG export without comparison. Present dependency maintenance/licensing/security footprint, encoding determinism and later decode/export needs.

## G3 — First real Agent provider/model

**Earliest lane:** P5-A5.

Recorded/fake providers remain CI authority. Before a paid/network provider becomes a reference run, pin provider/model/revision, settings, budget, vision use and API-cost boundary.

The existing trusted owner ChatGPT/Codex execution boundary may be reused only where a later frozen experiment explicitly permits it; this does not authorize unbounded retries.

## G4 — VLM/perceptual judge

**Earliest lane:** after deterministic QA exists.

Do not silently make a VLM score a correctness gate.

Owner decides whether a pinned VLM is used as bounded secondary perceptual evidence and where. Final aesthetic/product approval remains human. An aesthetic threshold must not create an autonomous retry-until-score loop unless the owner separately approves the exact bounded experiment, and even then the VLM is not ground truth.

## G5 — External/Aseprite/MCP scored baseline

**Earliest lane:** any scored benchmark freeze that proposes one.

Reference study is allowed earlier. Inclusion as a scored competitor requires owner approval after confirming implementation/version, license/tool availability, fair matched prompt/model/budget and automation reliability.

If fair harnessing is not possible, keep it qualitative rather than manufacturing a score.

PerfectPixel, sprite-gen and other external generators may be studied/compared under this principle; public availability alone is not permission to vendor or clone them.

## G6 — Home Windows self-hosted preview/provider runner

**Earliest lane:** P6-V6; owner-approved trusted runner boundary already exists for explicit owner-triggered workflows.

Never connect public pull-request events directly to the owner machine.

Any new workflow must preserve owner/manual trigger policy, explicit runner labels, secret-minimal execution, bounded concurrency/resource usage and artifact retention. Provider calls must never become mandatory portable CI.

## G7 — Simple-creature promotion

**Earliest lane:** after P8-B6 in the dedicated P10 lane.

**Owner decision recorded 2026-08-17:** simple creatures/animals were an approved long-term product destination. P10 completed with retained owner-accepted simple-creature evidence.

That historical success remains valid but does not override the later G8/P11 generator-strategy pivot.

## G8 — Humanoid direct-authoring promotion

**Historical lane:** G8 / issue #119.

**Owner decisions:**

- 2026-08-17: humanoid/character authoring approved as a long-term product destination, subject to creature evidence and explicit contracts.
- 2026-08-18: after two retained TracePixel humanoid owner REJECTs and one matched RAW comparison, owner selected **PIVOT**.

Disposition:

- `32111680356` remains technically valid / deterministic QA green / owner REJECT.
- `32118899233` remains technically valid / deterministic QA green / owner REJECT.
- matched RAW `32121042059` remains one-shot evidence; no rerun is authorized merely to improve the comparison.
- G8-H5 did **not** become product-quality PASS.
- issue #119 is closed as completed research/promotion evidence with owner REJECT + PIVOT.

Architecture consequence:

- stop treating humanoid-specific staged/direct PixelProgram generation as TracePixel's privileged production path,
- preserve direct authoring only as optional backend/control and possible precision local repair,
- preserve Canvas/PixelProgram/replay/QA/repair/evidence infrastructure,
- move active work to P11 generator-neutral quality control.

Do not reopen G8 to add H0-H3 schemas, skeleton/IK/physics or provider retries unless a future owner decision after P11 explicitly authorizes a new experiment.

## G9 — Animation / multi-frame promotion

**Current status after PIVOT:** blocked.

The 2026-08-17 owner direction that animation/sprite sheets are a desired long-term destination remains recorded, but the direct-animation implementation sequence is no longer automatically unlocked by finishing G8 contracts.

During P11:

- direct TracePixel animation/multi-frame generation stays blocked,
- do not build a new rig/skeleton/temporal authoring engine,
- external animation tools may be studied as references only,
- a future 32x32 animation/sprite-sheet **benchmark** may be proposed only after P11-P0 and an explicit owner promotion decision.

Any future animation benchmark must freeze frame/identity/motion/contact/root/pivot criteria, candidate backends, budgets and owner review rules before provider execution.

## G10 — Trace2D adapter experiment

**Earliest lane:** after evidence justifies a thin integration experiment.

Always explicit.

The decision is not "is TracePixel good?" but "does a thin generator-neutral quality/repair/evidence seam measurably improve Trace2D's existing Sprite/Asset workflow without contaminating Trace2D runtime authority?"

Required evidence before asking now includes:

- immutable B0/B1/G8 results,
- P11 generator-neutral candidate/QA/owner-review evidence,
- proposed provider-neutral RGBA/metadata/manifest seam,
- expected integration benchmark,
- confirmation that no Python/LLM/provider dependency enters Trace2D runtime/canonical asset state.

Positive P11 evidence does not silently approve G10.

## G11 — Post-P11 production-scope promotion

**Earliest lane:** P11-P0.

This is the next major owner decision after the pivot.

P11-P0 must present separate evidence for:

- static image quality,
- deterministic QA/normalization value,
- local-repair value and unaffected-region stability,
- provider/token/iteration/wall-time cost,
- owner review burden,
- retained failure behavior,
- comparison against honestly matched RAW/external/direct candidates.

The owner then chooses which, if any, direction is promoted:

- continue generator-neutral static production breadth,
- open a 32x32 animation/sprite-sheet benchmark,
- keep TracePixel-direct only as repair/control,
- retire more of direct generation,
- consider G10 Trace2D adapter work,
- stop/contract the project if the quality-controller thesis is not earning its complexity.

None is automatic.

## Resolved-decision recording

When the owner resolves a gate:

1. record the decision and rationale in the active issue/contract,
2. update `PROJECT_STATUS.md` if it affects future continuation,
3. update `config/tracepixel.core-lane.json` only when execution order/current child changes,
4. preserve frozen negative/scored evidence,
5. do not ask the same question again unless new evidence materially invalidates the recorded decision.
