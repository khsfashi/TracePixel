# Benchmark Contract

Status: preregistration skeleton. Scored cohorts must not begin until task fixtures, baselines, budgets and scoring rules are frozen in a commit.

## 1. Question

TracePixel is not benchmarked on "can AI make pretty pixel art?" alone.

The primary question is:

> For small constrained game assets, does a staged deterministic Agent surface improve successful completion, exact rule compliance, iteration cost and repairability compared with lower-level or image-generation baselines?

## 2. Baseline families

B0 should include as many of the following as can be pinned and run fairly:

1. **Raw LLM Python/Pillow** — model receives the task and writes image-producing code.
2. **Raw primitive Agent** — same model family, limited to low-level pixel/geometric tools without staged TracePixel guidance.
3. **Texel-Studio-like tool Agent** — reference architecture or a documented matched reimplementation when direct harnessing is impractical.
4. **Aseprite MCP Agent** — pinned reviewed MCP implementation where licensing/tool availability permits.
5. **Image generation -> deterministic postprocess** — general image generator followed by resize/quantization/alpha cleanup under a frozen recipe.
6. **TracePixel staged Agent** — same task constraints and comparable model budget.
7. Optional human baseline for a small subset, measured separately rather than mixed into automated ranking.

Do not claim a competitor result from an incompatible prompt/model/budget. If a direct matched run is impossible, report the reference qualitatively instead of manufacturing a score.

## 3. Difficulty ladder

Initial B0 tasks should avoid humanoid identity/animation complexity.

```text
T0 symbols/simple shapes
T1 coin/key/potion/gem/food
T2 sword/shield/chest/lantern/book
T3 rock/tree/barrel/furniture/props
T4 tileable blocks / simple terrain tiles
T5 simple creature (promotion gate)
T6 humanoid (later)
T7 animation / multi-frame consistency (later)
```

B0 should concentrate on T1-T3 with a small T0 sanity set. T4 requires explicit tiling metrics. T5+ are not needed to prove the first product claim.

## 4. Deterministic score

Task-specific rules are frozen before generation. Candidate metrics include:

- exact width/height,
- valid alpha/background contract,
- palette membership and maximum palette size,
- requested occupied bounds/margins,
- connected-component constraints,
- isolated-pixel count/rules,
- exact symmetry when explicitly required,
- required region/color presence when structurally specified,
- edge equality for tileable assets,
- operation/IR validity,
- deterministic replay equality.

Each task declares which metrics apply. Do not retroactively invent a metric because one method happened to look bad.

## 5. Perceptual score

Keep perceptual evaluation separate from structural success.

Candidate dimensions:

- recognizability,
- readability at native 1x scale,
- visual hierarchy,
- style coherence,
- aesthetic preference.

Use blind human ranking for final claims where practical. A pinned VLM judge may provide secondary repeatable evidence but is not ground truth and must not silently override deterministic rules.

## 6. Agent Complexity Budget

Every Agent run should record when available:

- input tokens,
- output tokens,
- tool calls,
- distinct operation/tool concepts exposed,
- canvas/visual observation calls,
- iterations/revisions,
- changed pixels per revision,
- wall time,
- provider/API cost,
- peak process memory for representative local workloads,
- human interventions,
- failure category.

Failure taxonomy should distinguish at least budget exhaustion, timeout, transport/provider failure, invalid operation/IR, deterministic verifier rejection, semantic/visual failure and human rejection.

## 7. Matched-run rules

For a scored comparison:

- freeze task text and hidden expected structural constraints,
- pin repository commit and baseline versions,
- pin model/provider identifiers and available generation settings,
- use equivalent task information across methods,
- set token/tool/time/cost budgets before runs,
- define retry policy before runs,
- record all attempts including unsuccessful ones,
- use multiple trials for nondeterministic methods,
- keep development-visible and held-out sets distinct.

## 8. B0 purpose

B0 is an architecture diagnostic, not a final marketing claim.

It should answer:

- Is staged authoring better than raw primitive calls?
- Does Pixel IR reduce invalid/verbose output?
- Which asset complexity tier breaks first?
- Where do token/tool budgets go?
- Which deterministic operations genuinely reduce iterations?
- Does a generated-image baseline win perceptually while losing exact constraints, and where?

B0 results may change the later authoring surface, but the frozen B0 cohort itself is preserved as historical evidence.

## 9. B1 entry gate

B1 begins only after B0 postmortem-driven changes are implemented. B1 uses held-out task variants frozen before scoring and tests generalization rather than rerunning B0 until TracePixel wins.
