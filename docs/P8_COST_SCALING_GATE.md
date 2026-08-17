# P8-C0 Batch Cost-Scaling Gate

Status: **mandatory checkpoint after P8-B1 and before P8-B2.**

P8-C0 exists because frozen B1 evidence showed that the full TracePixel staged path was already materially more expensive than the matched raw baseline. Mean TracePixel/raw ratios were approximately 5.06x input tokens, 4.67x output tokens, 4.94x provider calls/iterations and 4.58x wall time.

The first production-breadth question is therefore not "can TracePixel generate more asset classes?" It is "does AssetSet execution preserve bounded, attributable cost, or does batching add another uncontrolled multiplier?"

## Claim boundary

P8-C0 does **not** prove the existing per-member staged path is cost-optimal and does not erase the B1 ~5x overhead.

P8-C0 may prove only this narrower claim:

> For a bounded AssetSet, batch orchestration does not introduce hidden provider/token work or sibling-wide retry/restart amplification beyond the retained member executions, and aggregate budgets/concurrency remain enforced and auditable.

If that claim cannot be supported, P8-B2 and later breadth work stay blocked.

## Required P8-B1 telemetry

Each retained member execution must identify at least:

- immutable member/request identity,
- final member status,
- provider-call count,
- input-token count,
- output-token count,
- retry count and reason,
- repair-cycle count and reason,
- cache/reuse decision and source identity where applicable,
- member wall time,
- deterministic QA/perceptual/complexity/provenance references already required by the member pipeline.

The retained AssetSet execution must identify at least:

- declared `max_concurrency`,
- observed peak live member count,
- aggregate provider-call/input-token/output-token totals,
- aggregate retry/repair totals,
- aggregate wall time,
- aggregate declared budgets and whether each was enforced,
- failed member identities without deleting successful sibling evidence,
- scheduler/orchestration provider-call and token totals as an explicit separate field, even when zero.

## Hard accounting invariants

For one retained AssetSet execution:

```text
aggregate_provider_calls == sum(member.provider_calls) + scheduler_provider_calls
aggregate_input_tokens  == sum(member.input_tokens)  + scheduler_input_tokens
aggregate_output_tokens == sum(member.output_tokens) + scheduler_output_tokens
```

Before P8-B2, the scheduler/orchestrator itself must satisfy:

```text
scheduler_provider_calls == 0
scheduler_input_tokens == 0
scheduler_output_tokens == 0
```

Cross-asset provider work for aesthetic consistency belongs to later explicitly budgeted contracts and must never be smuggled into the batch scheduler.

A cache hit may reduce member cost. It must never make cost disappear from evidence: the retained member result records that the member was reused and which immutable result/request identity justified reuse.

## Failure-isolation cost invariant

A member failure, retry or repair must not cause already-successful unchanged siblings to be regenerated merely because they share one AssetSet execution.

P8-C0 evidence must include a failure-isolation case proving that:

- at least one member can fail or require member-local retry/repair,
- successful siblings remain retained,
- successful sibling request/result identities remain unchanged,
- successful siblings incur no additional provider calls/tokens solely due to the other member's failure,
- resuming/retrying targets only the affected member unless an explicit later contract invalidates a shared digest-pinned dependency.

## Concurrency and memory boundary

The executor must retain:

```text
observed_peak_live_members <= declared_max_concurrency
```

Scheduling may reduce wall-clock latency through bounded concurrency, but it may not increase provider fan-out beyond the declared bound or retain `N` live raster/provider workspaces when only `C` members are admitted.

P8-C0 should report wall-time behavior, but host/network timing is descriptive evidence rather than a brittle deterministic CI threshold. Structural concurrency and budget enforcement are the correctness boundary.

## Aggregate budget enforcement

Budgets are admission/runtime limits, not post-hoc dashboard numbers.

The executor must stop admitting or advancing work before an operation that would knowingly exceed a finite aggregate budget. A budget-exhausted member/set result must retain the partial evidence needed to explain where the budget was consumed.

At minimum, P8-C0 verifies finite enforcement for provider calls and wall time. If token budgets are available before provider invocation they should be enforced prospectively; otherwise token consumption must still be exactly attributed and the limitation documented rather than silently treated as a hard pre-call guarantee.

## Evidence shape

P8-C0 must commit a provider-free/recorded deterministic checkpoint for CI authority and retain at least one representative bounded AssetSet execution shape with multiple members and `max_concurrency > 1`.

If an owner-approved real-provider run is used for production-cost evidence, it must pin provider/model/settings/request digests and retain provider-reported token/call telemetry. Real-provider evidence supplements but does not replace the deterministic structural accounting checks.

The checkpoint report must include:

- member count and concurrency,
- member-level cost rows,
- aggregate totals,
- scheduler-only cost totals,
- budget outcomes,
- failure-isolation outcome,
- cache/reuse outcome where exercised,
- descriptive wall-time result,
- explicit statement that P8-C0 does not claim the B1 single-asset ~5x cost is solved.

## Promotion rule

The lane transition is fixed:

```text
P8-B1 -> P8-C0 -> P8-B2
```

P8-B1 must never hand off directly to P8-B2. P8-B2/B3/B4/B5/B6 must not start while P8-C0 is red, missing or unevidenced.

Creature, humanoid and animation promotion is later still: none belongs in P8, and each requires its own sequential post-P8 evidence gate after P8-B6.
