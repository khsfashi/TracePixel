# P11-X1 — Owner experiment / review protocol

Status: implemented as a provider-free protocol checkpoint. Active lane authority remains issue #151 and `config/tracepixel.core-lane.json`.

## Purpose

P11-X1 makes the post-pivot owner loop executable and recoverable without making deterministic QA, a VLM, or an aesthetic score the final product-quality authority.

The protocol is implemented by `tracepixel.owner_review` and keeps one JSON-compatible session in the following state sequence:

```text
experiment-frozen
 -> ready-for-owner-run
 -> running
 -> awaiting-owner-review
 -> accepted | repair-requested | rejected-stop
```

No provider call is required to implement or validate this protocol.

## Frozen experiment authority

`freeze_owner_experiment()` preregisters the facts that must not expand after a result is seen:

- experiment/task/asset and canvas identity,
- candidate backend set,
- frozen request reference,
- provider/model/revision reference,
- deterministic checks,
- human review criteria,
- retention prefix,
- provider call/input token/output token/wall-time limits,
- repair and regeneration limits.

The canonical experiment JSON is SHA-256 bound by `experiment_sha256`. Later validation fails closed if the experiment contents are changed without rebuilding the session from a newly frozen experiment.

## Explicit owner trigger

A provider/external run cannot enter `running` directly from `experiment-frozen`.

`authorize_owner_run()` records the exact owner source reference and moves the session to `ready-for-owner-run`. Only `begin_owner_run()` may then enter `running`.

This is a protocol boundary, not a provider executor. Later P11 benchmark workflows may use it to prove that a bounded run was owner-triggered.

## Mandatory review stop

`attach_owner_review_package()` validates actual run usage against the frozen budget and then records:

- run identity and measured usage,
- candidate identity/backend,
- exact candidate RGBA digest,
- native PNG ref + SHA-256,
- enlarged preview ref + SHA-256,
- deterministic QA evidence ref + SHA-256,
- complexity/cost evidence ref + SHA-256.

The only resulting state is `awaiting-owner-review`.

A fresh `@GitHub TracePixel 다음 작업 진행해줘` continuation that finds this state must surface those exact artifacts/evidence and the frozen criteria, then stop before another provider call.

## Natural-language owner feedback

The owner may respond naturally. The agent converts only explicit meaning into `record_owner_review()` arguments.

Unspecified frozen criteria are written as `unresolved`. An overall `REJECT` without criterion detail therefore does not fabricate criterion failures, region hints, or stage hints.

Final states are:

- `accepted`: exact owner acceptance; no repair intake,
- `repair-requested`: exact owner rejection feedback plus remaining preregistered repair budget,
- `rejected-stop`: retained negative result with no further repair request.

## P7 reuse

P11-X1 does not create another repair-feedback authority.

When the owner explicitly requests repair, `record_owner_review()` lowers the supplied feedback into the existing `tracepixel.feedback-intake.v1` contract:

- `authority = owner_human`,
- `human_rejection = true`,
- target asset/task/canvas come from the frozen experiment,
- target `artifact_sha256` is the exact reviewed native PNG digest,
- no score is synthesized,
- `stage_hint` and `region_hint` remain `null` unless the owner actually supplied information that justifies them.

The existing P7 validator remains the authority for that intake.

## Authority boundary

Every valid session freezes:

```text
human: repository-owner
deterministic_qa: retained-separate
perceptual: owner-human-only
aesthetic_auto_accept: forbidden
```

Deterministic QA may still reject exact objective defects, but its green state never promotes an image to owner acceptance.

## Provider-free checkpoint

`python -m evidence.p11_x1.checkpoint` proves the complete protocol path through `repair-requested` using synthetic digests and zero provider calls. Unit tests additionally lock:

- explicit owner authorization before running,
- budget overrun rejection,
- experiment digest tamper rejection,
- mandatory `awaiting-owner-review` stop,
- exact native PNG binding,
- conservative unresolved criteria,
- reuse of P7 feedback intake,
- no invented repair feedback after an overall rejection.

## Next child

After this checkpoint and the full portable CI are green, the core lane advances to **P11-X2 — deterministic candidate QA + normalization seam**.

X2 must remain generator-neutral and objective. It must not add anatomy/style/beauty truth, another perceptual authority, or provider retries.
