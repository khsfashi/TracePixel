# Agent Complexity Budget telemetry

P5-A3 adds a machine-readable evidence layer around the existing P5-A2 bounded edit loop. Telemetry is observational evidence only: it cannot validate Pixel IR, mutate the authoritative `Canvas`, decide deterministic QA, or turn provider/model state into canonical project state.

The measured entry point is:

```python
run_bounded_edit_loop_with_telemetry(...)
```

It delegates authoritative work to `run_bounded_edit_loop(...)` and returns the unchanged A2 `AgentLoopResult` beside one closed `tracepixel.agent-complexity-telemetry.v1` record.

## v1 fields

The record captures:

- `input_tokens` / `output_tokens`: exact aggregate provider usage when every completed provider call reports that metric; otherwise `null`. A zero-provider-call run records `0`.
- `tool_calls`: attempted `AgentProvider.propose(...)` calls.
- `operation_calls`: validated PixelProgram operation records that were actually accepted and applied.
- `exposed_concept_count`: distinct provider-visible JSON field paths observed across requests, excluding `schema` markers and normalizing list indices. This is a tokenizer-independent surface-complexity proxy, not a semantic-quality score.
- `visual_observation_calls`: actual `AgentPreviewObserver.observe(...)` calls.
- `iterations`: provider decision attempts. A3 keeps this separate from tool calls so later tool surfaces can diverge without redefining the evidence schema.
- `revisions`: accepted Canvas revisions.
- `changed_pixels`: sum of unique coordinates whose stored RGBA value actually changed in each accepted revision.
- `wall_time_ns`: monotonic elapsed wall time for the measured wrapper. This field is intentionally nondeterministic evidence.
- `api_cost_usd_micros`: exact aggregate cost in micro-US-dollars when every completed provider call reports it; otherwise `null`. Integer microunits avoid floating-point accumulation drift.
- `human_interventions`: explicit external count supplied to the measured run; the autonomous default is `0`.
- `failure_category`: `null` for `finished`, a stable `budget.*` category for bounded stops, or `contract.<AgentLoopContractError.code>` when the A2 deterministic contract rejects the run.

## Optional provider usage hook

A provider adapter may implement the separate runtime-checkable `AgentProviderUsageSource` protocol:

```python
def last_usage(self) -> AgentProviderUsage | None:
    ...
```

`AgentProviderUsage` contains only provider-neutral evidence fields:

- input tokens,
- output tokens,
- API cost in USD microunits.

No vendor response object, SDK type, model identifier, network retry state, or conversation object crosses into core telemetry. Providers that do not expose usage remain valid A0/A2 providers; token and cost aggregates become `null` after a provider call rather than being guessed.

Malformed/non-`AgentProviderUsage` optional samples are treated as unavailable evidence and do not affect raster execution.

## Accepted-work accounting

A3 observes the A2 loop without adding a second full-raster snapshot. For each proposed PixelProgram it records only the unique touched coordinates and their packed RGBA values before A2 validation/execution. The observation is committed to telemetry only when A2 subsequently reaches deterministic QA, which means the edit passed validation and budget preflight and was applied.

Therefore an invalid or over-budget proposal can increment `tool_calls`/`iterations`, but it does not increment `operation_calls`, `revisions`, or `changed_pixels`.

For `E` serialized edits and `U` unique touched coordinates in a proposal, this bookkeeping remains `O(E + U)` time and `O(U)` auxiliary memory. It does not allocate a second `width * height * 4` raster.

## Failure evidence

Normal budget exhaustion still returns the ordinary A2 result. The measured wrapper maps it to a stable telemetry category:

```text
iteration_budget_exhausted -> budget.iteration
tool_budget_exhausted      -> budget.tool
operation_budget_exhausted -> budget.operation
pixel_edit_budget_exhausted -> budget.pixel_edit
```

An A2 `AgentLoopContractError` is re-raised as `AgentMeasuredLoopError`, preserving the original exception in `.cause` and exposing the evidence collected so far in `.telemetry`. This keeps malformed candidate/configuration failures inspectable without changing A2 itself.

External provider/network exceptions remain external adapter failures and are not reinterpreted as deterministic correctness.

## Scope boundary

P5-A3 does not add a real provider/model, provider SDK, network dependency, secret, retry policy, VLM/perceptual judge, or recorded-provider checkpoint. Those remain P5-A4/P5-A5 and owner-gated scope where documented.
