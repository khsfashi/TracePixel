# Bounded provider-neutral Agent edit loop

P5-A2 connects the P5-A0 provider seam and P5-A1 compact observation to existing deterministic Pixel IR execution and P4 QA without selecting a provider, model, SDK, retry policy, network transport, or cost envelope.

The authority direction is now executable:

```text
instruction + compact observation
  -> AgentProvider.propose(...)
  -> validate provider envelope + PixelProgram
  -> budget preflight
  -> deterministic PixelProgram execution
  -> deterministic QA evaluator
  -> compact observation
  -> revise while findings remain, otherwise finish
```

Provider output is still candidate data. Validation and budget checks complete before a candidate can mutate the authoritative `Canvas`.

## Explicit budget v1

`tracepixel.agent-loop-budget.v1` is a closed required input. The loop has no hidden default budget:

```json
{
  "schema": "tracepixel.agent-loop-budget.v1",
  "max_iterations": 4,
  "max_tool_calls": 4,
  "max_operations": 16,
  "max_pixel_edits": 256
}
```

All limits are exact non-negative integers. In A2 one `AgentProvider.propose` invocation consumes one iteration and one tool call. They remain separate controls so either ceiling can stop orchestration deterministically and later tool surfaces do not require redefining the contract.

`max_operations` counts validated PixelProgram operation records. `max_pixel_edits` additionally bounds the total serialized pixel edits inside those operations so a single `set_pixels` operation cannot bypass the work bound.

Budget exhaustion is a normal `AgentLoopResult.status` and never applies an over-budget candidate:

```text
iteration_budget_exhausted
tool_budget_exhausted
operation_budget_exhausted
pixel_edit_budget_exhausted
```

The deterministic check order is iteration, tool call, operation, then pixel-edit budget. A proposed program whose cumulative operation or edit count would exceed its remaining budget is rejected before any raster mutation.

## Finish / revise rule

A2 does not ask a model to declare correctness. After every accepted edit, the caller-provided `AgentQaEvaluator` returns the existing typed Q5 findings contract.

- zero selected Q5 findings -> `finished`
- one or more selected Q5 findings -> revise, subject to budget

The initial Canvas is evaluated before the first provider call. If it already has zero findings, the loop returns `finished` with revision `0`, makes no provider call, and does not generate an optional preview.

This rule is deliberately narrow. Q5 only represents explicitly selected deterministic checks. Style, readability, identity, semantic resemblance, and other perceptual judgments are not silently promoted to correctness by A2.

## PixelProgram-only edit lane

The A0 provider seam still accepts both `pixel_program` and `stage_plan` candidate kinds. The A2 bounded edit loop accepts only `pixel_program` proposals because it edits an existing authoritative Canvas revision in place.

A valid `stage_plan` proposal is therefore rejected by A2 with `unsupported_edit_proposal`; this does not remove StagePlan from the provider-neutral interface or change P3 staged-authoring authority.

The proposed PixelProgram canvas must also exactly match the validated ArtIntent canvas before execution.

## Compact revision context

A proposal made against current revision `r` produces current revision `r + 1` after a successful deterministic apply. The compact `recent` record stores revision `r`, the source revision the proposal responded to.

A2 records only the already-required compact A1 summary fields:

- source revision,
- current stage,
- proposal kind,
- operation count,
- actual changed-pixel count.

Actual changed pixels are computed without copying the full raster. A2 snapshots only unique coordinates touched by the validated PixelProgram, applies the program, then compares those coordinates against the new authoritative bytes. For `E` serialized edits and `U` unique touched coordinates, this bookkeeping is `O(E + U)` time and `O(U)` additional memory.

Only the newest four summaries are retained by the existing A1 observation bound.

## Optional visual observation

`AgentPreviewObserver` is opt-in. No PNG is produced by default. When provided, it is invoked only while deterministic findings remain and a subsequent provider decision is needed. Its returned `AgentPreviewFrame` is passed through the existing A1 preview validation and 64 KiB decoded-size ceiling.

This avoids preview generation after a clean initial state or after the finishing edit. P5-A3 may count these observation calls as telemetry, but A2 does not introduce telemetry itself.

## Failure boundary

`AgentLoopContractError` is the stable deterministic A2 rejection surface for malformed budgets, invalid context, invalid provider proposals, unsupported edit proposal kinds, proposal/canvas mismatch, or invalid compact observations.

Provider/network exceptions raised by an external adapter are not converted into raster authority and are not interpreted as deterministic QA. Provider retry/network policy remains outside A2.

## Deliberate deferrals

P5-A2 does **not** add:

- token/cost/wall-time or aggregate complexity telemetry — P5-A3,
- a dedicated recorded/fake-provider CI checkpoint — P5-A4,
- a real provider/model/network adapter — P5-A5 / owner gate G3,
- VLM/perceptual correctness — owner gate G4.

Normal unit tests use deterministic fake providers and the existing Q0/Q5 QA path; no network or secrets are required.
