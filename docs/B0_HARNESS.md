# B0 matched harness

B0-H0 implements the common, provider-neutral result/retention layer for the frozen B0-v1 cohort. It does **not** run scored attempts and does not implement the method-specific baseline adapters reserved for B0-B0.

## Freeze identity

Every scheduled/result identity cites the authoritative B0-F0 freeze commit:

`c4b31288867fd4c4cf5ea3664808bd6f47cca1db`

The preregistration file remains `evidence/b0/preregistration.v1.json`; its exact byte SHA-256 is recorded in the materialized schedule.

## Matched schedule

The harness computes the schedule directly from the frozen task order, scored-method order, and trial count. B0-v1 therefore materializes exactly 28 primary attempts:

`7 tasks x 2 methods x 2 trials = 28 attempts`

Primary attempt IDs are deterministic. The only additional attempt identity permitted by H0 is one `rerun-1` record after a retained `void_infrastructure` primary failure before provider invocation. That void record must carry a reason and full fix commit SHA. A rerun cannot itself be voided again.

## Information matching

`visible_task_packet()` exposes only:

- task ID,
- tier,
- exact frozen `visible_text`.

It never exposes `hidden_structural_constraints`. B0-B0 adapters must construct provider requests from this visible packet plus only their frozen method-specific authoring-surface instructions.

## One result schema

All methods use `tracepixel.b0-attempt-result.v1` with the same layers:

- frozen attempt identity,
- provider-invoked/completion flags,
- frozen failure taxonomy,
- optional structured infrastructure-void record,
- deterministic per-rule structural results,
- raw telemetry envelope,
- later human-review envelope,
- retained artifact hashes/sizes,
- optional notes.

There is no composite winner field.

A non-completing attempt still materializes every task-applicable frozen structural rule as failed, giving structural fraction `0 / applicable_rules`. A completing attempt must provide every applicable frozen rule exactly once; partial or invented rule sets are rejected.

## Attempt retention

`write_attempt_record()` derives the immutable path from the frozen identity:

`<results-root>/<freeze-commit>/<method>/<task>/trial-NN[/rerun suffix]`

It requires the five always-retained payload files from the preregistration contract, computes SHA-256 and byte size from the exact payload bytes, generates `attempt-manifest.json`, and creates the attempt directory with `exist_ok=False`. An existing attempt path is never overwritten.

Optional `final.rgba`, `final.png`, `preview-8x.png`, and later sanitized evidence may be retained when produced. Authentication material must never be supplied as retained payload.

## Blind human review

The frozen ordering key is implemented exactly as SHA-256 of:

`<task_id>|<trial_index>|<method_id>`

Method labels are not required to derive review order.

## H0 boundary

Portable CI may load the frozen contract, materialize the schedule, validate schemas/retention behavior, and run synthetic unit tests. It performs no provider/network call and starts no scored attempt.

Next child after H0 acceptance is **B0-B0 baseline adapters**. That child must wire both frozen methods to this common harness without changing any B0-F0 parameter.
