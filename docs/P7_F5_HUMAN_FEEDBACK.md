# P7-F5 Human Feedback Contract

P7-F5 closes the targeted-repair loop without converting deterministic QA into authoring completion and without turning repository-owner judgment into deterministic truth.

The contract is `tracepixel.human-feedback.v1`.

## Reviewed evidence

Every F5 record retains the complete validated `tracepixel.repair-evidence.v1` object from P7-F4 and records the SHA-256 of its canonical JSON bytes. The review therefore stays bound to the exact F3 execution, before/after PNG identities, final deterministic QA evidence, and static comparison gallery that the owner inspected.

F5 does not rerun F3/F4 and does not regenerate review artifacts.

## Separate completion states

F5 deliberately records two independent statuses:

- `deterministic_qa_status`: `no-findings` or `findings-present`, derived only from retained F3 QA evidence,
- `human_authoring_status`: `accepted` or `repair-requested`, derived only from the explicit repository-owner decision.

`composite_completion` is always `not-defined`.

This means a deterministic `no-findings` result never auto-accepts the artwork. The owner may still request another bounded repair. Conversely, human acceptance does not erase or override deterministic findings if they are present.

This is the P7 fix for the B0 failure mode where staged authoring could terminate as soon as structural QA passed even though later authoring stages had not produced an acceptable visual result.

## Acceptance

`decision = accept` requires:

- an explicit bounded `source_ref`,
- a bounded owner summary,
- no follow-up `feedback_intake`.

No VLM, score aggregation, deterministic rule, or empty-QA shortcut can create acceptance implicitly.

## Repair request and loop closure

`decision = request_repair` requires a complete `tracepixel.feedback-intake.v1` object that is immediately valid for the next P7-F0 cycle.

That feedback intake must:

- target the same asset id, task id, and canvas as the reviewed F4 evidence,
- set `target.artifact_sha256` to the exact F4 `after/native.png` encoded-byte SHA-256,
- contain only `owner_human` feedback items,
- record `human_rejection = true` on every repair-request item.

The owner may provide bounded stage/region hints. F5 does not infer missing stage/region information from prose or scores; P7-F1 retains the existing conservative localization behavior.

The closed loop is therefore:

```text
F4 exact before/after evidence
 -> explicit owner review
 -> accept
```

or:

```text
F4 exact before/after evidence
 -> explicit owner repair request
 -> exact F0 feedback intake bound to after/native.png
 -> F1 localization
 -> F2 repair plan
 -> F3 execution + re-QA
 -> F4 evidence
 -> F5 review
```

## Authority boundary

The F5 authority record is fixed to:

```json
{
  "human": "repository-owner",
  "deterministic_qa": "retained-not-overridden",
  "perceptual": "owner-human-only",
  "vlm": "not-used"
}
```

P7-F5 does not cross G4. A future VLM/perceptual judge still requires the explicit owner gate.

## Benchmark boundary

Frozen B0 evidence remains immutable. P7 behavior is not validated by rerunning or relabeling B0.

After P7 acceptance, the architecture must be evaluated under the newly frozen held-out B1 cohort. B1 keeps deterministic structural results, perceptual evaluation, and complexity evidence separate rather than defining a universal composite art-quality score.
